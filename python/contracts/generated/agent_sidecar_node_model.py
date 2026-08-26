"""Auto-generated from contracts/schema."""

from typing import TypedDict


class AgentSidecarNodeModel(TypedDict, total=False):
    node: str
    account_id: str
    base_url: str
    api_key: str
    model: str
    provider_type: str
