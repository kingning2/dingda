"""LangGraph 可用 AI 平台注册表 — 设置页 catalog 的唯一真相源。

与 ``ProviderKind`` / ``normalize_provider_type`` 对齐：这里注册了哪些，
前端「添加账号」就能选哪些。新增平台只改本文件。
"""

from __future__ import annotations

from typing import TypedDict


class ProviderCatalogItem(TypedDict, total=False):
    """对齐 Contract ``AiProvider``。"""

    id: str
    kind: str
    name: str
    base_url: str
    default_model: str


_REGISTRY: list[ProviderCatalogItem] = []
_REGISTERED_IDS: set[str] = set()


def register_provider(item: ProviderCatalogItem) -> None:
    """注册一个可选平台（id 唯一；重复 id 覆盖）。"""
    provider_id = item["id"]
    if provider_id in _REGISTERED_IDS:
        _REGISTRY[:] = [row for row in _REGISTRY if row["id"] != provider_id]
        _REGISTERED_IDS.discard(provider_id)
    _REGISTRY.append(item)
    _REGISTERED_IDS.add(provider_id)


def providers_catalog() -> list[ProviderCatalogItem]:
    """返回当前已注册平台（只读副本）。"""
    return [dict(item) for item in _REGISTRY]


def _register_builtins() -> None:
    """内置平台 — 覆盖 ``ProviderKind`` 与常见 OpenAI 兼容端点。"""
    # openai_compatible 族
    register_provider(
        {
            "id": "deepseek",
            "kind": "deepseek",
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "default_model": "deepseek-chat",
        }
    )
    register_provider(
        {
            "id": "doubao",
            "kind": "doubao",
            "name": "豆包",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        }
    )
    register_provider(
        {
            "id": "openai",
            "kind": "openai_compatible",
            "name": "OpenAI",
            "base_url": "https://api.openai.com/v1",
        }
    )
    register_provider(
        {
            "id": "qwen",
            "kind": "dashscope",
            "name": "通义千问",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        }
    )
    register_provider(
        {
            "id": "ollama",
            "kind": "openai_compatible",
            "name": "本地 Ollama",
            "base_url": "http://localhost:11434/v1",
            "default_model": "qwen2.5",
        }
    )
    # ProviderKind.ANTHROPIC — 需兼容网关或后续原生客户端
    register_provider(
        {
            "id": "anthropic",
            "kind": "anthropic",
            "name": "Anthropic",
            "base_url": "https://api.anthropic.com",
            "default_model": "claude-sonnet-4-20250514",
        }
    )
    # ProviderKind.GEMINI
    register_provider(
        {
            "id": "gemini",
            "kind": "gemini",
            "name": "Google Gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "default_model": "gemini-2.0-flash",
        }
    )
    # ProviderKind.DASHSCOPE_APP
    register_provider(
        {
            "id": "dashscope_app",
            "kind": "dashscope_app",
            "name": "百炼应用",
            "base_url": "https://dashscope.aliyuncs.com/api/v1/apps",
        }
    )


_register_builtins()
