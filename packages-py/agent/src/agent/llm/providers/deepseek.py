"""DeepSeek 供应商目录。"""

from __future__ import annotations

from agent.llm.providers.base import CatalogProvider

PROVIDER = CatalogProvider(
    id="deepseek",
    name="DeepSeek",
    base_url="https://api.deepseek.com",
    # deepseek-chat / deepseek-reasoner 已于 2026-07-24 停用且不自动重定向。
    default_model="deepseek-flash",
    supports_models=True,
    api_key_envs=("DEEPSEEK_API_KEY",),
)
