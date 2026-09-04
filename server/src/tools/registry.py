"""Tool 注册表：按名查找并执行 Tool。

职责：
    聚合各 Tool 模块（契约 + run_*）；供 MCP 与产品 Agent 统一 invoke。

设计说明：
    - 选品：search / product / compare（每工具一个 ``tools/<name>.py``）
    - 浏览器平台经 Crawler → BrowserPort；ali1688 经 ApiCrawler → Channel
    - 不在此 import Playwright

使用示例：
    out = await call_tool("search", {"platform": "xianyu", "query": "露营椅"})
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from src.shared.errors import AppError
from src.tools.compare import (
    DEFAULT_TIMEOUT_S as COMPARE_TIMEOUT_S,
    TOOL_DESCRIPTION as COMPARE_DESCRIPTION,
    TOOL_NAME as COMPARE_NAME,
    CompareInput,
    CompareOutput,
    run_compare,
)
from src.tools.product import (
    DEFAULT_TIMEOUT_S as PRODUCT_TIMEOUT_S,
    TOOL_DESCRIPTION as PRODUCT_DESCRIPTION,
    TOOL_NAME as PRODUCT_NAME,
    ProductInput,
    ProductOutput,
    run_product,
)
from src.tools.search import (
    DEFAULT_TIMEOUT_S as SEARCH_TIMEOUT_S,
    TOOL_DESCRIPTION as SEARCH_DESCRIPTION,
    TOOL_NAME as SEARCH_NAME,
    SearchInput,
    SearchOutput,
    run_search,
)

logger = logging.getLogger("dingda.tools.registry")


@dataclass(frozen=True)
class ToolSpec:
    """单个 Tool 的注册信息。"""

    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[..., Awaitable[BaseModel]]
    timeout_s: float


def _spec(
    name: str,
    description: str,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    handler: Callable[..., Awaitable[BaseModel]],
    timeout_s: float,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        input_model=input_model,
        output_model=output_model,
        handler=handler,
        timeout_s=timeout_s,
    )


_TOOLS: dict[str, ToolSpec] = {
    SEARCH_NAME: _spec(
        SEARCH_NAME,
        SEARCH_DESCRIPTION,
        SearchInput,
        SearchOutput,
        run_search,  # type: ignore[arg-type]
        SEARCH_TIMEOUT_S,
    ),
    PRODUCT_NAME: _spec(
        PRODUCT_NAME,
        PRODUCT_DESCRIPTION,
        ProductInput,
        ProductOutput,
        run_product,  # type: ignore[arg-type]
        PRODUCT_TIMEOUT_S,
    ),
    COMPARE_NAME: _spec(
        COMPARE_NAME,
        COMPARE_DESCRIPTION,
        CompareInput,
        CompareOutput,
        run_compare,  # type: ignore[arg-type]
        COMPARE_TIMEOUT_S,
    ),
}


def list_tools() -> list[ToolSpec]:
    """已注册 Tool 列表。"""
    return sorted(_TOOLS.values(), key=lambda item: item.name)


def get_tool(name: str) -> ToolSpec:
    """按名取 Tool；未知则抛 AppError。"""
    spec = _TOOLS.get(name)
    if spec is None:
        raise AppError("tool.unknown", f"未知 Tool：{name}", status_code=404)
    return spec


async def call_tool(name: str, payload: dict[str, Any]) -> BaseModel:
    """校验入参并执行 Tool。"""
    logger.info("registry call name=%s", name)
    spec = get_tool(name)
    inp = spec.input_model.model_validate(payload)
    out = await spec.handler(inp)
    logger.info("registry call done name=%s", name)
    return out
