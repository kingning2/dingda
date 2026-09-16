"""Tool 注册表：按名查找并执行 Tool。

职责：
    聚合各 Tool 模块（契约 + run_*）；供产品 Agent 与工具子进程统一 invoke。

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

from core.errors import AppError
from tools.browse import (
    DEFAULT_TIMEOUT_S as BROWSE_TIMEOUT_S,
    TOOL_DESCRIPTION as BROWSE_DESCRIPTION,
    TOOL_NAME as BROWSE_NAME,
    BrowseInput,
    BrowseOutput,
    run_browse,
)
from tools.child_cancel import (
    DEFAULT_TIMEOUT_S as CHILD_CANCEL_TIMEOUT_S,
    TOOL_DESCRIPTION as CHILD_CANCEL_DESCRIPTION,
    TOOL_NAME as CHILD_CANCEL_NAME,
    ChildCancelInput,
    ChildCancelOutput,
    run_child_cancel,
)
from tools.child_resume import (
    DEFAULT_TIMEOUT_S as CHILD_RESUME_TIMEOUT_S,
    TOOL_DESCRIPTION as CHILD_RESUME_DESCRIPTION,
    TOOL_NAME as CHILD_RESUME_NAME,
    ChildResumeInput,
    ChildResumeOutput,
    run_child_resume,
)
from tools.child_run import (
    DEFAULT_TIMEOUT_S as CHILD_RUN_TIMEOUT_S,
    TOOL_DESCRIPTION as CHILD_RUN_DESCRIPTION,
    TOOL_NAME as CHILD_RUN_NAME,
    ChildRunInput,
    ChildRunOutput,
    run_child_run,
)
from tools.child_status import (
    DEFAULT_TIMEOUT_S as CHILD_STATUS_TIMEOUT_S,
    TOOL_DESCRIPTION as CHILD_STATUS_DESCRIPTION,
    TOOL_NAME as CHILD_STATUS_NAME,
    ChildStatusInput,
    ChildStatusOutput,
    run_child_status,
)
from tools.compare import (
    DEFAULT_TIMEOUT_S as COMPARE_TIMEOUT_S,
    TOOL_DESCRIPTION as COMPARE_DESCRIPTION,
    TOOL_NAME as COMPARE_NAME,
    CompareInput,
    CompareOutput,
    run_compare,
)
from tools.live_push import make_live_frame_handler
from tools.login import (
    DEFAULT_TIMEOUT_S as LOGIN_TIMEOUT_S,
    TOOL_DESCRIPTION as LOGIN_DESCRIPTION,
    TOOL_NAME as LOGIN_NAME,
    LoginInput,
    LoginOutput,
    run_login,
)
from tools.preview import (
    DEFAULT_TIMEOUT_S as PREVIEW_TIMEOUT_S,
    TOOL_DESCRIPTION as PREVIEW_DESCRIPTION,
    TOOL_NAME as PREVIEW_NAME,
    PreviewInput,
    PreviewOutput,
    run_preview,
)
from tools.product import (
    DEFAULT_TIMEOUT_S as PRODUCT_TIMEOUT_S,
    TOOL_DESCRIPTION as PRODUCT_DESCRIPTION,
    TOOL_NAME as PRODUCT_NAME,
    ProductInput,
    ProductOutput,
    run_product,
)
from tools.repair_dom import (
    DEFAULT_TIMEOUT_S as REPAIR_DOM_TIMEOUT_S,
    TOOL_DESCRIPTION as REPAIR_DOM_DESCRIPTION,
    TOOL_NAME as REPAIR_DOM_NAME,
    RepairDomInput,
    RepairDomOutput,
    run_repair_dom,
)
from tools.search import (
    DEFAULT_TIMEOUT_S as SEARCH_TIMEOUT_S,
    TOOL_DESCRIPTION as SEARCH_DESCRIPTION,
    TOOL_NAME as SEARCH_NAME,
    SearchInput,
    SearchOutput,
    run_search,
)
from tools.validate import (
    DEFAULT_TIMEOUT_S as VALIDATE_TIMEOUT_S,
    TOOL_DESCRIPTION as VALIDATE_DESCRIPTION,
    TOOL_NAME as VALIDATE_NAME,
    ValidateInput,
    ValidateOutput,
    run_validate,
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
    # 只给特定 agent 用（如修复子 agent 的校验工具）：默认面不暴露
    internal_only: bool = False


def _spec(
    name: str,
    description: str,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    handler: Callable[..., Awaitable[BaseModel]],
    timeout_s: float,
    *,
    internal_only: bool = False,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        input_model=input_model,
        output_model=output_model,
        handler=handler,
        timeout_s=timeout_s,
        internal_only=internal_only,
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
    BROWSE_NAME: _spec(
        BROWSE_NAME,
        BROWSE_DESCRIPTION,
        BrowseInput,
        BrowseOutput,
        run_browse,  # type: ignore[arg-type]
        BROWSE_TIMEOUT_S,
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
    CHILD_RUN_NAME: _spec(
        CHILD_RUN_NAME,
        CHILD_RUN_DESCRIPTION,
        ChildRunInput,
        ChildRunOutput,
        run_child_run,  # type: ignore[arg-type]
        CHILD_RUN_TIMEOUT_S,
    ),
    CHILD_RESUME_NAME: _spec(
        CHILD_RESUME_NAME,
        CHILD_RESUME_DESCRIPTION,
        ChildResumeInput,
        ChildResumeOutput,
        run_child_resume,  # type: ignore[arg-type]
        CHILD_RESUME_TIMEOUT_S,
    ),
    CHILD_CANCEL_NAME: _spec(
        CHILD_CANCEL_NAME,
        CHILD_CANCEL_DESCRIPTION,
        ChildCancelInput,
        ChildCancelOutput,
        run_child_cancel,  # type: ignore[arg-type]
        CHILD_CANCEL_TIMEOUT_S,
    ),
    CHILD_STATUS_NAME: _spec(
        CHILD_STATUS_NAME,
        CHILD_STATUS_DESCRIPTION,
        ChildStatusInput,
        ChildStatusOutput,
        run_child_status,  # type: ignore[arg-type]
        CHILD_STATUS_TIMEOUT_S,
    ),
    REPAIR_DOM_NAME: _spec(
        REPAIR_DOM_NAME,
        REPAIR_DOM_DESCRIPTION,
        RepairDomInput,
        RepairDomOutput,
        run_repair_dom,  # type: ignore[arg-type]
        REPAIR_DOM_TIMEOUT_S,
    ),
    # 只给修复子 agent 用：靠 DINGDA_VALIDATE_URL 回打修复现场那个页面
    VALIDATE_NAME: _spec(
        VALIDATE_NAME,
        VALIDATE_DESCRIPTION,
        ValidateInput,
        ValidateOutput,
        run_validate,  # type: ignore[arg-type]
        VALIDATE_TIMEOUT_S,
        internal_only=True,
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
    if name in {"search", "product", "preview", "browse"} and live is None:
        logger.warning(
            "tool %s without DINGDA_AGENT_RUN_ID：浏览器直播不会推到 UI",
            name,
        )
    if live is not None and name in {"search", "product", "browse"}:
        out = await spec.handler(inp, on_live_frame=live, live_frame_enabled=True)
    elif live is not None and name == "login":
        out = await spec.handler(inp, on_live_frame=live)
    else:
        out = await spec.handler(inp)
    logger.info("registry call done name=%s", name)
    return out
