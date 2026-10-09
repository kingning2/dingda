"""Tool 注册表：自动发现 tools/ 下的工具目录并按名执行。

职责：
    聚合各 Tool（契约 + run_*）；供 MCP 与产品 Agent 统一 invoke。

设计说明：
    - 每个工具一个 ``tools/<name>/`` 子包，``__init__.py`` 导出契约、run_* 与 ``spec``
    - 注册表用 ``pkgutil.iter_modules`` 自动发现子包，读取其 ``spec`` 属性；
      新增工具 = 新建目录 + 构造 spec（或 ``python -m tools.scaffold``），无需改本文件
    - 支撑模块（account_cookie / recovery / live_push）保持平铺，不会被误认成工具
    - 浏览器平台经 Crawler → BrowserPort；ali1688 经 ApiCrawler → Channel
    - 不在此 import Playwright

使用示例：
    out = await call_tool("search", {"platform": "xianyu", "query": "露营椅"})
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from core.errors import AppError
from tools.live_push import make_live_frame_handler
from tools.spec import ToolSpec

logger = logging.getLogger("dingda.tools.registry")

_SKIP = {"scaffold"}
# registry 是普通模块没有 __path__；用文件位置定位包目录
_TOOLS_PATH = [str(Path(__file__).resolve().parent)]


def _discover() -> dict[str, ToolSpec]:
    """扫描 tools/ 下的子包，收集每个包导出的 ``spec``。"""
    found: dict[str, ToolSpec] = {}
    for info in pkgutil.iter_modules(_TOOLS_PATH):
        if not info.ispkg or info.name in _SKIP:
            continue
        module = importlib.import_module(f"tools.{info.name}")
        spec = getattr(module, "spec", None)
        if isinstance(spec, ToolSpec):
            found[spec.name] = spec
        else:
            logger.warning("tool package %s has no spec；已跳过", info.name)
    logger.info("registry discovered %s tools: %s", len(found), sorted(found))
    return found


_TOOLS: dict[str, ToolSpec] = _discover()


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
