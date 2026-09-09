"""外部 CLI 子进程启动与取消。

职责：
    解析 runtime → 注入 MCP → asyncio 起进程 → 流式解析 stdout 为 AgentEvent。
    同时 drain live_hub，把 ``preview`` 推送的 browserFrame 并入 SSE。

设计说明：
    - 内存登记 run_id → process，供 cancel
    - prompt 默认写 stdin（Codex/Claude）
    - ``DINGDA_AGENT_RUN_ID`` 注入 MCP，跨进程投帧
    - 控制台按「一轮会话块」打日志（开头配置 / 流式输出 / MCP 工具 / 结尾线）
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from src.agent.runtimes import live_hub
from src.agent.runtimes.mcp_inject import SERVER_NAME, apply_mcp_inject
from src.agent.runtimes.prompts import compose_agent_prompt, dingda_system_prompt
from src.agent.runtimes.registry import get_runtime, resolve_binary
from src.agent.runtimes.stream import parse_lines
from src.crawler.ocr import warm_ocr
from src.shared.errors import AppError
from src.tools.registry import list_tools

logger = logging.getLogger("dingda.agent.runtimes.spawn")

_RUNS: dict[str, asyncio.subprocess.Process] = {}
_TEXT_FLUSH_CHARS = 120


def _api_base() -> str:
    return (
        os.getenv("DINGDA_API_BASE", "").strip() or "http://127.0.0.1:8787"
    ).rstrip("/")


def _mcp_config_line(mcp_mode: str) -> str:
    tools = ", ".join(spec.name for spec in list_tools()) or "(无)"
    prompt_chars = len(dingda_system_prompt())
    return (
        f"MCP 服务器 `{SERVER_NAME}`（工具：{tools}）；"
        f"注入方式={mcp_mode}；"
        f"提示词=dingda-system.md（{prompt_chars} 字）"
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
            return f"拉详情 item_id={item_id}"
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
    ) -> None:
        self._runtime_id = runtime_id
        self._model = model.strip() or "default"
        self._user_prompt = (user_prompt or "").strip() or "(空)"
        self._mcp_mode = mcp_mode
        self._kind: str | None = None
        self._parts: list[str] = []
        self._closed = False

    def start(self) -> None:
        logger.info("----- %s/%s 开始工作-----", self._runtime_id, self._model)
        logger.info("输入： %s", self._user_prompt)
        logger.info("当前配置： %s", _mcp_config_line(self._mcp_mode))
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
        # 末尾无换行的尾巴也要打
        if text and not text.endswith("\n") and lines:
            pass
        elif text.endswith("\n") and text.splitlines() == lines:
            pass
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


async def cancel_run(run_id: str) -> None:
    """杀掉正在跑的 CLI。"""
    proc = _RUNS.pop(run_id.strip(), None)
    live_hub.close_run(run_id)
    if proc is None:
        return
    logger.info("runtime cancel run=%s", run_id)
    if proc.returncode is None:
        proc.kill()
        try:
            await proc.wait()
        except Exception:  # noqa: BLE001
            pass


async def run_cli(
    runtime_id: str,
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
) -> AsyncIterator[dict[str, Any]]:
    """启动外部 CLI 并 yield AgentEvent dict。"""
    rid = (run_id or f"run-{uuid.uuid4().hex[:12]}").strip()
    # OCR 仅 Agent 选品图文用：开跑即后台预热，与思考并行，不挡首轮
    asyncio.create_task(asyncio.to_thread(warm_ocr))
    try:
        spec = get_runtime(runtime_id)
    except KeyError as exc:
        raise AppError(
            "agent.runtime_unsupported",
            f"Python 侧暂未接入 runtime：{runtime_id}（当前支持 codex/claude/opencode）",
            status_code=501,
        ) from exc

    binary = resolve_binary(spec, preferred=executable)
    if binary is None:
        raise AppError(
            "agent.runtime_missing",
            f"未找到 {spec.name} 可执行文件（请安装或设置 {spec.path_env}，"
            f"或使用叮答下载到 ~/.dingda/v2/runtimes/{spec.id}/）",
            status_code=404,
        )

    workdir = Path(cwd).resolve() if cwd and cwd.strip() else Path.cwd()
    workdir.mkdir(parents=True, exist_ok=True)
    ctx = {
        "cwd": str(workdir),
        "model_id": model_id,
        "session_id": session_id,
        "reasoning": reasoning,
        "extra_allowed_dirs": extra_allowed_dirs or [],
    }
    args = list(spec.build_args(ctx))
    env = {**os.environ, "PYTHONUTF8": "1"}
    api_base = _api_base()
    args = apply_mcp_inject(
        spec.mcp_mode,
        cwd=workdir,
        args=args,
        env=env,
        run_id=rid,
        api_base=api_base,
    )
    full_prompt = compose_agent_prompt(
        prompt,
        platform_hint=platform_hint,
        resume=bool(str(session_id or "").strip()),
    )
    session_log = _RunSessionLog(
        runtime_id=spec.id,
        model=str(model_id or "").strip() or "default",
        user_prompt=prompt,
        mcp_mode=spec.mcp_mode,
    )
    session_log.start()

    # 启动细节降到 debug，避免打断会话块
    logger.debug(
        "runtime spawn id=%s bin=%s run=%s args=%s",
        spec.id,
        binary,
        rid,
        args[:12],
    )
    live_hub.open_run(rid)
    yield {"type": "runStarted", "runtimeId": spec.id, "runId": rid}

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

    if spec.prompt_via_stdin and proc.stdin is not None:
        data = full_prompt.encode("utf-8")
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
                line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=0.25)
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
            for event in parse_lines(spec.stream_format, text, state=parse_state):
                session_log.emit(event)
                yield event
        for frame_event in live_hub.drain(rid):
            session_log.emit(frame_event)
            yield frame_event
        code = await proc.wait()
        done = {"type": "runCompleted", "exitCode": int(code or 0)}
        session_log.emit(done)
        yield done
        logger.debug("runtime done id=%s run=%s code=%s", spec.id, rid, code)
    except asyncio.CancelledError:
        await cancel_run(rid)
        cancel_err = {"type": "error", "message": "已取消"}
        session_log.emit(cancel_err)
        yield cancel_err
        done = {"type": "runCompleted", "exitCode": 130}
        session_log.emit(done)
        yield done
        raise
    finally:
        session_log.close()
        _RUNS.pop(rid, None)
        live_hub.close_run(rid)
