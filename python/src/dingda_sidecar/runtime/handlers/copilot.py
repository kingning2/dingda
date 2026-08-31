"""Copilot 副驾 — pipe RPC 启动/取消 + HTTP SSE（仅测试/遗留）。

产品路径：Rust 经 pipe ``/v1/copilot/run_start`` 启动，事件经 ``copilot.run`` 推送。
"""

from __future__ import annotations

import logging
import queue
import uuid
from dataclasses import dataclass
from typing import Any

from dingda_sidecar.agent.workflows.task_copilot import (
    CopilotRun,
    get_run,
    make_pipe_sink,
    register_run,
    run_copilot_run,
)

logger = logging.getLogger("dingda.runtime.copilot")


@dataclass
class CopilotStream:
    """一轮副驾对话的事件流句柄（供 HTTP SSE 写循环消费，非产品路径）。"""

    run_id: str
    events: queue.Queue[dict[str, Any]]
    done: Any
    cancelled: Any


def _parse_messages(raw: Any) -> list[Any]:
    """AG-UI 消息 → LangChain 消息；非法 role 降级为 user。"""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    by_role: dict[str, type] = {
        "user": HumanMessage,
        "assistant": AIMessage,
        "system": SystemMessage,
        "tool": HumanMessage,
    }
    messages: list[Any] = []
    if not isinstance(raw, list):
        return messages
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user")
        content = item.get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        text = str(content or "")
        if not text:
            continue
        messages.append(by_role.get(role, HumanMessage)(content=text))
    return messages


def _resolve_credentials(payload: dict[str, Any]) -> tuple[str, str, str]:
    """从 pipe 请求体解析 AI 凭据（Rust 注入 default_* 字段）。"""
    raw_forwarded = payload.get("forwardedProps")
    forwarded = raw_forwarded if isinstance(raw_forwarded, dict) else {}
    api_key = str(
        payload.get("default_api_key") or forwarded.get("default_api_key") or "",
    )
    base_url = str(
        payload.get("default_base_url") or forwarded.get("default_base_url") or "",
    )
    model = str(
        payload.get("default_model") or forwarded.get("default_model") or "",
    )
    return api_key, base_url, model


def _build_run(payload: dict[str, Any], *, sink: Any) -> CopilotRun:
    api_key, base_url, model = _resolve_credentials(payload)
    return CopilotRun(
        run_id=str(payload.get("runId") or payload.get("run_id") or "").strip()
        or str(uuid.uuid4()),
        thread_id=str(payload.get("threadId") or payload.get("thread_id") or "").strip()
        or "default",
        messages=_parse_messages(payload.get("messages")),
        state=payload.get("state") if isinstance(payload.get("state"), dict) else {},
        settings_api_key=api_key,
        settings_base_url=base_url,
        settings_model=model,
        sink=sink,
    )


def _start_run(run: CopilotRun) -> None:
    register_run(run)
    run_copilot_run(run)
    logger.info(
        "copilot.stream.start run_id=%s thread=%s model=%s",
        run.run_id,
        run.thread_id,
        run.settings_model or "-",
        extra={"run_id": run.run_id, "feature": "copilot"},
    )


def handle_copilot_run_start(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """pipe RPC：启动一轮副驾对话，事件经 copilot.run 推送。"""
    del trace_id
    body = payload if isinstance(payload, dict) else {}
    run = _build_run(body, sink=make_pipe_sink())
    _start_run(run)
    return {"ok": True, "run_id": run.run_id, "thread_id": run.thread_id}


def handle_copilot_run_abort(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """pipe RPC：取消指定副驾对话轮。"""
    del trace_id
    body = payload if isinstance(payload, dict) else {}
    run_id = str(body.get("run_id") or body.get("runId") or "").strip()
    if not run_id:
        return {"ok": False, "message": "run_id 必填"}
    run = get_run(run_id)
    if run is None:
        return {"ok": True, "message": "run 已结束或不存在"}
    run.cancelled.set()
    return {"ok": True, "run_id": run_id}


def start_copilot_stream(payload: dict[str, Any]) -> CopilotStream:
    """HTTP SSE 遗留路径：解析请求体并写入队列（非产品路径）。"""
    import threading

    events: queue.Queue[dict[str, Any]] = queue.Queue()
    done = threading.Event()
    cancelled = threading.Event()
    run = _build_run(payload, sink=events.put)
    run.cancelled = cancelled
    run.done = done
    _start_run(run)
    return CopilotStream(run_id=run.run_id, events=events, done=done, cancelled=cancelled)


def abort_copilot_stream(stream: CopilotStream) -> None:
    """HTTP SSE 客户端断开时取消本轮。"""
    stream.cancelled.set()


def handle_copilot_http_info(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """pipe RPC 端口发现（遗留；产品路径不再依赖前端直连 HTTP）。"""
    del payload, trace_id
    from dingda_sidecar.runtime.server import copilot_http_port

    port = copilot_http_port()
    return {"ok": port is not None, "port": port}
