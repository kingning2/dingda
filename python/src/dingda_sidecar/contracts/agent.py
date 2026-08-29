"""Auto-generated from contracts/schema."""

from __future__ import annotations

from typing import TypedDict

from .channel import ChannelCookie


class AgentIpcPingRequest(TypedDict, total=False):
    trace_id: str


class AgentIpcPingResponse(TypedDict, total=False):
    ok: bool
    trace_id: str


class AgentSidecarNodeModel(TypedDict, total=False):
    node: str
    account_id: str
    base_url: str
    api_key: str
    model: str
    provider_type: str


class AgentSidecarPingRequest(TypedDict, total=False):
    trace_id: str


class AgentSidecarPingResponse(TypedDict, total=False):
    ok: bool
    trace_id: str


class AgentSidecarRunCancelRequest(TypedDict, total=False):
    run_id: str
    trace_id: str


class AgentSidecarRunCancelResponse(TypedDict, total=False):
    ok: bool
    run_id: str
    state: str
    message: str


class AgentSidecarRunControlRequest(TypedDict, total=False):
    run_id: str
    action: str
    node: str
    node_model: AgentSidecarNodeModel
    trace_id: str


class AgentSidecarRunControlResponse(TypedDict, total=False):
    ok: bool
    run_id: str
    state: str
    message: str


class AgentSidecarRunStartRequest(TypedDict, total=False):
    run_id: str
    user: str
    system: str
    kind: str
    node_models: list[AgentSidecarNodeModel]
    default_base_url: str
    default_api_key: str
    default_model: str
    resume_from_run_id: str
    resume_state_json: str
    resume_node: str
    trace_id: str
    channel_account_id: str
    cookies: list[ChannelCookie]


class AgentSidecarRunStartResponse(TypedDict, total=False):
    ok: bool
    run_id: str
    state: str
    message: str


class AgentSidecarRunStatusRequest(TypedDict, total=False):
    run_id: str
    since_index: int
    trace_id: str


class AgentSidecarRunStatusResponse(TypedDict, total=False):
    ok: bool
    run_id: str
    state: str
    current_node: str
    completed_nodes: list[str]
    steps: list[AgentSidecarRunStep]
    reply: str
    error: str
    error_kind: str
    failed_node: str
    message: str


class AgentSidecarRunStep(TypedDict, total=False):
    node: str
    index: int
    status: str
    label: str
    detail: str
    error_kind: str
    account_id: str
    model: str
    content: str
    state_before_json: str
