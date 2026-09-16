"""外部 CLI Runtime 插座。

职责：
    统一一次 CLI 会话的生命周期：解析可执行文件 → 拼 prompt（工具走 skill 注入）→ spawn
    → 流式解析 → 会话日志；顺带提供压缩方法。
    每个 CLI 的差异只留在 ``runtimes/<id>.py`` 的插头里。

设计说明：
    - 禁止插头自己 ``create_subprocess`` / 自己拼 system 前言 / 自己找二进制
    - 父 / 子 agent 的差异（提示词怎么拼 / 工具注入方式 / cwd 落哪）全在 ``roles/``
      的角色插头里；本文件只按 ``role`` 取那几条策略，不写「是不是子 agent」
    - **工具注入统一走 skill**：宿主把 Skill 正文拼进 prompt，并把资源复制到
      ``.dingda-skills/``；工具注入只有这一条路径
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
import sys
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any, ClassVar

from cli import live as live_hub
from cli.prompts import load_persona
from cli.roles import AgentRole, get_role
from cli.stream import parse_lines
from crawler.ocr import warm_ocr
from core.config import api_base_url
from core.errors import AppError

logger = logging.getLogger("dingda.cli.base")

_RUNS: dict[str, asyncio.subprocess.Process] = {}
_TEXT_FLUSH_CHARS = 120


def _api_base() -> str:
    """当前 Server 的 HTTP 基址（解析规则见 ``core.config.api_base_url``）。"""
    return api_base_url()


def _tool_entry_dirs() -> list[str]:
    """``tool`` 入口可能所在的目录（当前解释器 → DINGDA_PYTHON 指定解释器）。

    解释器同级的 ``Scripts`` / ``bin`` 就是 console script 落地处。子进程继承的 PATH
    未必包含它（server 不一定从已激活的 venv 启动），而 skill 命令写的是裸 ``tool``，
    所以显式前置。
    """
    dirs: list[str] = []
    for raw in (sys.executable, (os.getenv("DINGDA_PYTHON") or "").strip()):
        if not raw:
            continue
        path = str(Path(raw).resolve().parent)
        if path not in dirs:
            dirs.append(path)
    return dirs


def _session_config_line(
    *,
    uses_system_prompt: bool = True,
    persona: str | None = None,
) -> str:
    """会话日志里的「当前配置」行。"""
    if uses_system_prompt and persona:
        prompt_note = f"角色人设（{len(load_persona(persona))} 字）"
    elif uses_system_prompt:
        prompt_note = "角色人设"
    else:
        prompt_note = "仅本次 prompt（不拼人设）"
    return f"工具注入：skill；提示词：{prompt_note}"


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
        uses_system_prompt: bool = True,
        persona: str | None = None,
    ) -> None:
        self._runtime_id = runtime_id
        self._model = model.strip() or "default"
        self._user_prompt = (user_prompt or "").strip() or "(空)"
        self._uses_system_prompt = uses_system_prompt
        self._persona = persona
        self._kind: str | None = None
        self._parts: list[str] = []
        self._closed = False

    def start(self) -> None:
        logger.info("----- %s/%s 开始工作-----", self._runtime_id, self._model)
        logger.info("输入： %s", self._user_prompt)
        logger.info(
            "当前配置： %s",
            _session_config_line(
                uses_system_prompt=self._uses_system_prompt,
                persona=self._persona,
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
            logger.info("工具： %s， %s", name, task)
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
    stream_format: ClassVar[str] = "codex-json"
    # prompt 写 stdin 的编码：plain=纯文本；claude-stream-json=一条 stream-json 消息
    stdin_format: ClassVar[str] = "plain"
    prompt_via_stdin: ClassVar[bool] = True
    fallback_binaries: ClassVar[tuple[str, ...]] = ()
    # 本 CLI 跑起来需要的额外环境变量（默认无）。
    extra_env: ClassVar[Mapping[str, str]] = {}

    @abstractmethod
    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """本 CLI 的命令行参数（含 sandbox / 模型 / 续聊）。"""

    def resolve_binary(self, *, preferred: str | None = None) -> Path | None:
        """解析可执行文件；探测顺序见 agents.resolve_binary。"""
        # 局部 import：agents 要 import 插头，插头 import 本模块
        from cli.agents import resolve_binary

        return resolve_binary(self, preferred=preferred)

    def compress_payload(
        self,
        payload: dict[str, Any],
        *,
        label: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """压要送进本 CLI 的大 JSON 载荷（目前是修复 prompt 的 dom_tree）。

        统一走 ``core.compress.compress_tool_payload``；关闭 / 未装 / 失败时透传。
        """
        from core.compress import compress_tool_payload

        return compress_tool_payload(payload, tool_name=label, model=model)

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
        context_messages: list[dict[str, Any]] | None = None,
        role: str | AgentRole | None = None,
        run_env: dict[str, str] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """起一次 CLI 会话并 yield AgentEvent dict。

        ``role`` 决定提示词怎么拼、注入哪些 Skill、cwd 落哪（见 roles/）。
        ``run_env`` 是本次运行才有的追加环境（如校验回打地址），叠在角色之上。
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
        # 裸 `tool` 入口要靠 PATH 找；Windows 上键名可能是 Path，按实际键名改写
        path_key = next((key for key in env if key.upper() == "PATH"), "PATH")
        env[path_key] = os.pathsep.join([*_tool_entry_dirs(), env.get(path_key, "")])
        # 插头自带的环境变量（对系统 node 之类是 no-op）
        env.update(self.extra_env)
        merged_env = {
            **session_role.session_env(),
            **session_role.run_env(),
            **(run_env or {}),
        }
        # 同一份会话 env 也给 CLI 进程：子 agent 可能靠 CLI 回打
        env.update(merged_env)
        # 推帧所需：search/login/preview 要把浏览器截图 POST 回来
        env.setdefault("DINGDA_AGENT_RUN_ID", rid)
        env.setdefault("DINGDA_API_BASE", _api_base())
        # 子会话继承父 runtime / model（编排工具读这些）
        env.setdefault("DINGDA_AGENT_RUNTIME", self.id)
        if model_id:
            env["DINGDA_LLM_MODEL"] = str(model_id).strip()
        has_session = bool(str(session_id or "").strip())
        full_prompt = session_role.compose_prompt(
            prompt,
            platform_hint=platform_hint,
            resume=has_session,
            workdir=workdir,
            # 有 CLI session 时记忆在 runtime 侧，勿再灌叮答历史
            context_messages=None if has_session else context_messages,
        )
        session_log = _RunSessionLog(
            runtime_id=self.id,
            model=str(model_id or "").strip() or "default",
            user_prompt=prompt,
            uses_system_prompt=session_role.uses_system_prompt,
            persona=session_role.persona,
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
