"""Auto-generated from contracts/schema."""

from typing import TypedDict


class AgentSidecarRunStatusRequest(TypedDict, total=False):
    run_id: str
    since_index: int
    trace_id: str
