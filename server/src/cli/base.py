"""外部 CLI Runtime 插座。

职责：
    统一一次 CLI 会话的生命周期：解析可执行文件 → 拼 prompt（工具走 skill 注入）→ spawn
    → 流式解析 → 会话日志；顺带提供压缩方法。
    每个 CLI 的差异只留在 ``runtimes/<id>.py`` 的插头里。

设计说明：
    - 禁止插头自己 ``create_subprocess`` / 自己拼 system 前言 / 自己找二进制
    - 父 / 子 agent 的差异（提示词怎么拼 / 工具注入方式 / cwd 落哪）全在 ``roles/``
      的角色插头里；本文件只按 ``role`` 取那几条策略，不写「是不是子 agent」
    - **工具注入统一走 skill**：runtime 读 skills 目录里的 ``dingda-crawl/SKILL.md``，
      角色 ``mcp_mode()`` 恒返回 ``"none"``，不再注入 MCP
    - 压缩是插座上的一个方法（``compress_payload``），不另立插座

使用示例：
    runtime = get_runtime("codex")
    async for event in runtime.run("搜闲鱼露营椅", run_id="run-1", role="parent"):
        ...
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, ClassVar

from src.cli.inject.mcp import SERVER_NAME, apply_mcp_inject
from src.cli.live import hub as live_hub
from src.cli.prompts import system_prompt
from src.cli.roles.base import AgentRole
from src.cli.roles.registry import get_role
from src.cli.stream.parse import parse_lines
from src.crawler.ocr import warm_ocr
from src.shared.errors import AppError

logger = logging.getLogger("dingda.cli.base")

_RUNS: dict[str, asyncio.subprocess.Process] = {}
_TEXT_FLUSH_CHARS = 120
# 载荷超过该字节数才压缩
COMPRESS_MIN_BYTES = 2048


def _api_base() -> str:
    return (
        os.getenv("DINGDA_API_BASE", "").strip() or "http://127.0.0.1:8787"
    ).rstrip("/")


def _mcp_config_line(
    mcp_mode: str,
    *,
    tools: list[str] | None = None,
    uses_system_prompt: bool = True,
) -> str:
    """会话日志里的「当前配置」行。

    工具注入已统一为 skill：``mcp_mode`` 恒为 ``"none"``，不再列 MCP 工具白名单。
    ``tools`` / ``mcp_mode`` 参数保留只为兼容旧调用形状。
    """
    prompt_note = (
        f"system.md（{len(system_prompt())} 字）"
        if uses_system_prompt
        else "仅本次 prompt（不拼父提示词）"
    )
    if mcp_mode == "none":
        # 注入方式已统一为 skill：工具由 runtime 读 skills 目录里的 SKILL.md 得到
        return f"工具注入：skill（未注入 MCP）；提示词：{prompt_note}"
    tools_note = ", ".join(tools) if tools else "全部"
    return (
        f"MCP 服务器 `{SERVER_NAME}`（工具：{tools_note}）；"
        f"注入方式={mcp_mode}；"
        f"提示词：{prompt_note}"
    )


def _describe_tool_task(name: str, raw_input: Any) -> str:
    """把工具入参收成一句「在干什么」。"""
    if not isinstance(raw_input, dict):
        return "开始执行"
    platform = str(raw_input.get("platform") or "").strip()
    if name == "search":
        query = str(raw_input.get("query") or "").strip()
        if platform and query:
            return f"在 {platform} 搜索「{query}」"
        if query:
            return f"搜索「{query}」"
        return "开始搜索"
    if name == "product":
        item_id = str(raw_input.get("item_id") or "").strip()
        if platform and item_id:
            return f"拉 {platform} 详情 item_id={item_id}"
        if item_id:
            return f"拉详情 {item_id}"
        return "拉商品详情"
    if name == "compare":
        return "比价 / 对照分析"
    if name == "login":
        plat = str(raw_input.get("platform") or platform or "").strip()
        return f"等待扫码登录 {plat}" if plat else "等待扫码登录"
    if name == "preview":
        url = str(raw_input.get("url") or "").strip()
        return f"预览网页 {url}" if url else "打开网页预览"
    bits = [
        f"{key}={value}"
        for key, value in raw_input.items()
        if value is not None and str(value).strip() and key not in {"cookie", "proxy_url"}
    ][:4]
    return "，".join(bits) if bits else "开始执行"


class _RunSessionLog:
    """一轮 CLI 会话的控制台块日志。"""

    def __init__(
        self,
        *,
        runtime_id: str,
        model: str,
        user_prompt: str,
        mcp_mode: str,
        tools: list[str] | None = None,
        uses_system_prompt: bool = True,
    ) -> None:
        self._runtime_id = runtime_id
        self._model = model.strip() or "default"
        self._user_prompt = (user_prompt or "").strip() or "(空)"
        self._mcp_mode = mcp_mode
        self._tools = tools
        self._uses_system_prompt = uses_system_prompt
        self._kind: str | None = None
        self._parts: list[str] = []
        self._closed = False

    def start(self) -> None:
        logger.info("----- %s/%s 开始工作-----", self._runtime_id, self._model)
        logger.info("输入： %s", self._user_prompt)
        logger.info(
            "当前配置： %s",
            _mcp_config_line(
                self._mcp_mode,
                tools=self._tools,
                uses_system_prompt=self._uses_system_prompt,
            ),
        )
        logger.info("输出：")

    def emit(self, event: dict[str, Any]) -> None:
        if self._closed:
            return
        kind = str(event.get("type") or "")
        if kind in {"thinking", "textDelta"}:
            text = event.get("text")
            if not isinstance(text, str) or not text:
                return
            if self._kind and self._kind != kind:
                self._flush_text()
            self._kind = kind
            self._parts.append(text)
            joined = "".join(self._parts)
            if "\n" in text or len(joined) >= _TEXT_FLUSH_CHARS:
                self._flush_text()
            return

        self._flush_text()
        if kind == "toolCall":
            name = str(event.get("name") or "tool").strip() or "tool"
            task = _describe_tool_task(name, event.get("input"))
            logger.info("mcp工具： %s， %s", name, task)
        elif kind == "error":
            logger.info("错误： %s", event.get("message") or "未知错误")
        elif kind == "runCompleted":
            self.close()

    def _flush_text(self) -> None:
        if not self._parts or not self._kind:
            self._kind = None
            self._parts.clear()
            return
        kind = self._kind
        text = "".join(self._parts)
        self._kind = None
        self._parts.clear()
        prefix = "（思考）" if kind == "thinking" else ""
        lines = text.splitlines()
        if not lines and text:
            lines = [text]
        for line in lines:
            if line == "" and not prefix:
                continue
            logger.info("%s%s", prefix, line)

    def close(self) -> None:
        if self._closed:
            return
        self._flush_text()
        logger.info("--------------------------------------")
        self._closed = True


class CliRuntime(ABC):
    """CLI Runtime 插座：管一次会话的生命周期，插头只写「本 CLI 长什么样」。"""

    id: ClassVar[str]
    name: ClassVar[str]
    binary: ClassVar[str]
    path_env: ClassVar[str]
    mcp_mode: ClassVar[str]
    stream_format: ClassVar[str] = "codex-json"
    # prompt 写 stdin 的编码：plain=纯文本；claude-stream-json=一条 stream-json 消息
    stdin_format: ClassVar[str] = "plain"
    prompt_via_stdin: ClassVar[bool] = True
    fallback_binaries: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """本 CLI 的命令行参数（含 sandbox / 模型 / 续聊）。"""

    def resolve_binary(self, *, preferred: str | None = None) -> Path | None:
        """解析可执行文件；探测顺序见 registry.resolve_binary。"""
        # 局部 import：registry 要 import 插头，插头 import 本模块
        from src.cli.registry import resolve_binary

        return resolve_binary(self, preferred=preferred)

    def compress_payload(
        self,
        payload: dict[str, Any],
        *,
        label: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """压要送进本 CLI 的大 JSON 载荷（目前是修复 prompt 的 dom_tree）。

        ``DINGDA_HEADROOM=0`` 或未装 headroom-ai 时透传。
        """
        if not _headroom_enabled():
            return payload
        raw = json.dumps(payload, ensure_ascii=False, default=str)
        if len(raw.encode("utf-8")) < COMPRESS_MIN_BYTES:
            return payload
        try:
            from headroom import compress
        except ImportError:
            logger.warning("headroom-ai 未安装，跳过 CLI 载荷压缩")
            return payload

        target = (model or _headroom_model()).strip() or _headroom_model()
        wrapped = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_dingda",
                        "type": "function",
                        "function": {"name": label, "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_dingda", "content": raw},
        ]
        try:
            result = compress(wrapped, model=target)
        except Exception:  # noqa: BLE001
            logger.exception("headroom CLI 载荷压缩失败，透传原文")
            return payload

        logger.info(
            "cli payload compress label=%s saved=%s before=%s after=%s",
            label,
            int(getattr(result, "tokens_saved", 0) or 0),
            int(getattr(result, "tokens_before", 0) or 0),
            int(getattr(result, "tokens_after", 0) or 0),
        )
        for msg in reversed(getattr(result, "messages", None) or []):
            if not isinstance(msg, dict) or msg.get("role") != "tool":
                continue
            content = msg.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("压缩结果非 JSON，保留原文 label=%s", label)
                return payload
            return parsed if isinstance(parsed, dict) else payload
        return payload

    def encode_stdin(self, prompt: str) -> bytes:
        """按本 CLI 的 stdin 约定编码 prompt。

        Claude 的 ``--input-format stream-json`` 收的是**一条 JSON 消息**，不是纯文本；
        直接灌纯文本会报 ``Error parsing streaming input line``。
        """
        text = prompt or ""
        if self.stdin_format == "claude-stream-json":
            line = json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": text}],
                    },
                },
                ensure_ascii=False,
            )
            return (line + "\n").encode("utf-8")
        return text.encode("utf-8")

    async def run(
        self,
        prompt: str,
        *,
        run_id: str | None = None,
        cwd: str | None = None,
        model_id: str | None = None,
        session_id: str | None = None,
        reasoning: str | None = None,
        executable: str | None = None,
        extra_allowed_dirs: list[str] | None = None,
        platform_hint: str | None = None,
        role: str | AgentRole | None = None,
        mcp_env: dict[str, str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """起一次 CLI 会话并 yield AgentEvent dict。

        ``role`` 决定提示词怎么拼、MCP 给不给（给哪些工具）、cwd 落哪（见 roles/）。
        ``mcp_env`` 是本次运行才有的 MCP 追加环境（如校验回打地址），叠在角色之上。
        """
        rid = (run_id or f"run-{uuid.uuid4().hex[:12]}").strip()
        # OCR 仅 Agent 选品图文用：开跑即后台预热，与思考并行，不挡首轮
        asyncio.create_task(asyncio.to_thread(warm_ocr))

        binary = self.resolve_binary(preferred=executable)
        if binary is None:
            raise AppError(
                "agent.runtime_missing",
                f"未找到 {self.name} 可执行文件（请安装或设置 {self.path_env}，"
                f"或使用叮答下载到 ~/.dingda/v2/runtimes/{self.id}/）",
                status_code=404,
            )

        session_role = get_role(role)
        workdir = session_role.workdir(cwd)
        workdir.mkdir(parents=True, exist_ok=True)
        ctx = {
            "cwd": str(workdir),
            "model_id": model_id,
            "session_id": session_id,
            "reasoning": reasoning,
            "extra_allowed_dirs": extra_allowed_dirs or [],
        }
        args = list(self.build_args(ctx))
        env = {**os.environ, "PYTHONUTF8": "1"}
        mcp_mode = session_role.mcp_mode(self.mcp_mode)
        session_mcp_env = {**session_role.mcp_env(), **(mcp_env or {})}
        # 同一份会话 env 也给 CLI 进程：子 agent 可能靠 CLI 回打（不一定走 MCP）
        env.update(session_mcp_env)
        # 推帧所需：无论是否注入 MCP，search/login/preview 都要把浏览器截图 POST 回来
        env.setdefault("DINGDA_AGENT_RUN_ID", rid)
        env.setdefault("DINGDA_API_BASE", _api_base())
        args = apply_mcp_inject(
            mcp_mode,
            cwd=workdir,
            args=args,
            env=env,
            run_id=rid,
            api_base=_api_base(),
            extra_env=session_mcp_env,
        )
        full_prompt = session_role.compose_prompt(
            prompt,
            platform_hint=platform_hint,
            resume=bool(str(session_id or "").strip()),
        )
        session_log = _RunSessionLog(
            runtime_id=self.id,
            model=str(model_id or "").strip() or "default",
            user_prompt=prompt,
            mcp_mode=mcp_mode,
            tools=None,
            uses_system_prompt=session_role.uses_system_prompt,
        )
        session_log.start()

        logger.debug(
            "runtime spawn id=%s bin=%s run=%s args=%s",
            self.id,
            binary,
            rid,
            args[:12],
        )
        live_hub.open_run(rid)
        yield {"type": "runStarted", "runtimeId": self.id, "runId": rid}

        proc = await asyncio.create_subprocess_exec(
            str(binary),
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(workdir),
            env=env,
        )
        _RUNS[rid] = proc

        if self.prompt_via_stdin and proc.stdin is not None:
            data = self.encode_stdin(full_prompt)
            proc.stdin.write(data)
            if not data.endswith(b"\n"):
                proc.stdin.write(b"\n")
            await proc.stdin.drain()
            proc.stdin.close()

        assert proc.stdout is not None
        parse_state: dict[str, Any] = {}
        try:
            while True:
                for frame_event in live_hub.drain(rid):
                    session_log.emit(frame_event)
                    yield frame_event
                try:
                    line_bytes = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=0.25
                    )
                except TimeoutError:
                    if proc.returncode is not None:
                        break
                    continue
                if not line_bytes:
                    if proc.returncode is not None:
                        break
                    await asyncio.sleep(0.05)
                    continue
                text = line_bytes.decode("utf-8", errors="replace")
                for event in parse_lines(self.stream_format, text, state=parse_state):
                    session_log.emit(event)
                    yield event
            for frame_event in live_hub.drain(rid):
                session_log.emit(frame_event)
                yield frame_event
            code = await proc.wait()
            done = {"type": "runCompleted", "exitCode": int(code or 0)}
            session_log.emit(done)
            yield done
            logger.debug("runtime done id=%s run=%s code=%s", self.id, rid, code)
        finally:
            _RUNS.pop(rid, None)
            session_log.close()


def _headroom_enabled() -> bool:
    value = os.getenv("DINGDA_HEADROOM", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _headroom_model() -> str:
    return os.getenv("DINGDA_LLM_MODEL", "gpt-4o").strip() or "gpt-4o"


async def cancel_run(run_id: str) -> None:
    """杀掉正在跑的 CLI。"""
    proc = _RUNS.pop(run_id.strip(), None)
    if proc is None or proc.returncode is not None:
        return
    logger.info("runtime cancel run=%s", run_id)
    try:
        proc.terminate()
    except ProcessLookupError:
        return
