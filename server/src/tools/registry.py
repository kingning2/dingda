"""Tool 注册表：按名查找并执行 Tool。

职责：
    聚合各 Tool 模块（契约 + run_*）；供 MCP 与产品 Agent 统一 invoke。

设计说明：
    - 选品：search / product / compare / preview / login（每工具一个 ``tools/<name>.py``）
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
from src.tools.live_push import make_live_frame_handler
from src.tools.login import (
    DEFAULT_TIMEOUT_S as LOGIN_TIMEOUT_S,
    TOOL_DESCRIPTION as LOGIN_DESCRIPTION,
    TOOL_NAME as LOGIN_NAME,
    LoginInput,
    LoginOutput,
    run_login,
)
from src.tools.preview import (
    DEFAULT_TIMEOUT_S as PREVIEW_TIMEOUT_S,
    TOOL_DESCRIPTION as PREVIEW_DESCRIPTION,
    TOOL_NAME as PREVIEW_NAME,
    PreviewInput,
    PreviewOutput,
    run_preview,
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
    PREVIEW_NAME: _spec(
        PREVIEW_NAME,
        PREVIEW_DESCRIPTION,
        PreviewInput,
        PreviewOutput,
        run_preview,  # type: ignore[arg-type]
        PREVIEW_TIMEOUT_S,
    ),
    LOGIN_NAME: _spec(
        LOGIN_NAME,
        LOGIN_DESCRIPTION,
        LoginInput,
        LoginOutput,
        run_login,  # type: ignore[arg-type]
        LOGIN_TIMEOUT_S,
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
    """校验入参并执行 Tool；Agent run 下自动挂直播推帧。"""
    logger.info("registry call name=%s", name)
    spec = get_tool(name)
    inp = spec.input_model.model_validate(payload)
    live = make_live_frame_handler()
    if name in {"search", "product", "preview"} and live is None:
        logger.warning(
            "tool %s without DINGDA_AGENT_RUN_ID：浏览器直播不会推到 UI",
            name,
        )
    if live is not None and name in {"search", "product"}:
        out = await spec.handler(inp, on_live_frame=live, live_frame_enabled=True)
    elif live is not None and name == "login":
        out = await spec.handler(inp, on_live_frame=live)
    else:
        out = await spec.handler(inp)
    logger.info("registry call done name=%s", name)
    return out
