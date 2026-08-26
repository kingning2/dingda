"""Auto-generated from contracts/schema."""

from typing import TypedDict
from .agent_sidecar_node_model import AgentSidecarNodeModel


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
