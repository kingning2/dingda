"""Auto-generated from contracts/schema."""

from typing import TypedDict
from .ai_account import AiAccount
from .ai_graph_models import AiGraphModels
from .ai_provider import AiProvider


class AiIpcConfigRequest(TypedDict, total=False):
    providers: list[AiProvider]
    accounts: list[AiAccount]
    graph_models: AiGraphModels
