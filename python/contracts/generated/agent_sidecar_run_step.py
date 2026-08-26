"""Auto-generated from contracts/schema."""

from typing import TypedDict


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
