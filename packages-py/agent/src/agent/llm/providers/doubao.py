"""豆包（火山方舟）供应商目录。

模型必须填推理接入点 ID（``ep-...``）。请求体默认开 thinking。
"""

from __future__ import annotations

from typing import Any

from agent.llm.providers.base import CatalogProvider

PROVIDER = CatalogProvider(
    id="doubao",
    name="豆包",
    # 尾缀 /api/v3 不能省。方舟 Coding Plan 走 /api/coding/v3，用
    # DINGDA_LLM_BASE_URL 覆盖。
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    default_model=None,
    supports_models=False,
    api_key_envs=("ARK_API_KEY",),
)

EXTRA_BODY: dict[str, Any] = {"thinking": {"type": "enabled"}}
"""方舟 chat 请求的额外字段。"""
