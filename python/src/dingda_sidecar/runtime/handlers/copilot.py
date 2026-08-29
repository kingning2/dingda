"""CopilotKit 副驾直连 HTTP — SSE 流组装 + 端口发现。

前端 CopilotKit HttpAgent 直连 sidecar 的 ``POST /v1/copilot/agui``
（SSE），本模块只负责解析 AG-UI 请求体、组装事件队列；
HTTP 读写与保活心跳在 ``runtime/server.py``。
"""

from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass
from typing import Any

from dingda_sidecar.agent.workflows.task_copilot import (
    CopilotRun,
    register_run,
    run_copilot_run,
)

logger = logging.getLogger("dingda.runtime.copilot")


@dataclass
class CopilotStream:
    """一轮副驾对话的事件流句柄（供 SSE 写循环消费）。"""

    run_id: str
    events: queue.Queue[dict[str, Any]]
    done: threading.Event
    cancelled: threading.Event


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


def start_copilot_stream(payload: dict[str, Any]) -> CopilotStream:
    """解析 AG-UI RunAgentInput，启动 worker 并返回事件流句柄。"""
    raw_forwarded = payload.get("forwardedProps")
    forwarded = raw_forwarded if isinstance(raw_forwarded, dict) else {}

    events: queue.Queue[dict[str, Any]] = queue.Queue()
    done = threading.Event()
    cancelled = threading.Event()

    run = CopilotRun(
        run_id=str(payload.get("runId") or "").strip() or uuid.uuid4().hex,
        thread_id=str(payload.get("threadId") or "").strip() or "default",
        messages=_parse_messages(payload.get("messages")),
        state=payload.get("state") if isinstance(payload.get("state"), dict) else {},
        settings_api_key=str(forwarded.get("default_api_key") or ""),
        settings_base_url=str(forwarded.get("default_base_url") or ""),
        settings_model=str(forwarded.get("default_model") or ""),
        sink=events.put,
        cancelled=cancelled,
        done=done,
    )
    register_run(run)
    run_copilot_run(run)
    logger.info(
        "copilot.stream.start run_id=%s thread=%s model=%s",
        run.run_id,
        run.thread_id,
        run.settings_model or "-",
        extra={"run_id": run.run_id, "feature": "copilot"},
    )
    return CopilotStream(run_id=run.run_id, events=events, done=done, cancelled=cancelled)


def abort_copilot_stream(stream: CopilotStream) -> None:
    """客户端断开时取消本轮。"""
    stream.cancelled.set()


def handle_copilot_http_info(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """pipe RPC 端口发现：返回副驾直连 HTTP 服务端口（未启动时 port 为 None）。"""
    del payload, trace_id
    from dingda_sidecar.runtime.server import copilot_http_port

    port = copilot_http_port()
    return {"ok": port is not None, "port": port}
