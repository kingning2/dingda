"""豆包 Coding Plan 供应商目录。

职责：
    提供火山方舟 Coding Plan 的 OpenAI 兼容地址；模型仍由用户显式选择。

设计说明：
    - Coding Plan 的计费与普通推理接入不同，地址尾缀必须是 ``/api/coding/v3``
    - Coding Plan 提供 OpenAI 兼容 ``/models``；表单先拉列表，仍保留手填兜底
    - 不猜默认模型；控制台给模型名就填模型名，给接入点就填 ``ep-...``
"""

from __future__ import annotations

from agent.llm.providers.base import CatalogProvider

PROVIDER = CatalogProvider(
    id="doubao-coding",
    name="豆包 Coding Plan",
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
    default_model=None,
    supports_models=True,
    api_key_envs=("ARK_CODING_API_KEY", "ARK_API_KEY"),
)
