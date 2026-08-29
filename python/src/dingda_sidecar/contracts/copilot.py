"""Auto-generated from contracts/schema."""

from __future__ import annotations

from typing import TypedDict


class CopilotAguiEvent(TypedDict, total=False):
    type: str
    thread_id: str
    run_id: str
    message_id: str
    role: str
    delta: str
    content: str
    tool_call_id: str
    tool_name: str
    args_delta: str
    message: str
    code: str


class CopilotCopilotMessage(TypedDict):
    id: str
    role: str
    content: str


class CopilotRunStartRequest(TypedDict, total=False):
    threadId: str
    runId: str
    messages: list[CopilotCopilotMessage]
    state: str
    forwardedProps: str


class CopilotRunStartResponse(TypedDict, total=False):
    content_type: str
    frames: list[CopilotAguiEvent]
