"""Auto-generated from contracts/schema."""

from typing import TypedDict
from .agent_sidecar_node_model import AgentSidecarNodeModel


class AgentSidecarRunControlRequest(TypedDict, total=False):
    run_id: str
    action: str
    node: str
    node_model: AgentSidecarNodeModel
    trace_id: str
