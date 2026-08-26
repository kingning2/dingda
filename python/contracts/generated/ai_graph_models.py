"""Auto-generated from contracts/schema."""

from typing import TypedDict
from .ai_graph_node_account import AiGraphNodeAccount


class AiGraphModels(TypedDict, total=False):
    node_accounts: list[AiGraphNodeAccount]
    failover_account_ids: list[str]
    failover_enabled: bool
