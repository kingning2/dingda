"""Auto-generated from contracts/schema."""

from __future__ import annotations

from typing import TypedDict


class AiAccount(TypedDict, total=False):
    id: str
    provider_id: str
    name: str
    api_key: str
    default_model: str


class AiGraphModels(TypedDict, total=False):
    node_accounts: list[AiGraphNodeAccount]
    failover_account_ids: list[str]
    failover_enabled: bool


class AiGraphNodeAccount(TypedDict):
    node: str
    account_id: str


class AiIpcConfigRequest(TypedDict, total=False):
    providers: list[AiProvider]
    accounts: list[AiAccount]
    graph_models: AiGraphModels


class AiIpcConfigResponse(TypedDict, total=False):
    providers: list[AiProvider]
    accounts: list[AiAccount]
    graph_models: AiGraphModels


class AiIpcListModelsRequest(TypedDict, total=False):
    base_url: str
    api_key: str
    kind: str


class AiIpcListModelsResponse(TypedDict):
    ok: bool
    message: str
    models: list[str]


class AiIpcProvidersCatalogResponse(TypedDict):
    providers: list[AiProvider]


class AiProvider(TypedDict, total=False):
    id: str
    kind: str
    name: str
    base_url: str
    default_model: str
