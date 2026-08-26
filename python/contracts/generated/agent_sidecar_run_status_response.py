"""Auto-generated from contracts/schema."""

from typing import TypedDict
from .agent_sidecar_run_step import AgentSidecarRunStep


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
