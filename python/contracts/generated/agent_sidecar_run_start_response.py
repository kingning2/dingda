"""Auto-generated from contracts/schema."""

from typing import TypedDict


class AgentSidecarRunStartResponse(TypedDict, total=False):
    ok: bool
    run_id: str
    state: str
    message: str
