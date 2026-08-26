"""Auto-generated from contracts/schema."""

from typing import TypedDict


class AgentSidecarRunCancelRequest(TypedDict, total=False):
    run_id: str
    trace_id: str
