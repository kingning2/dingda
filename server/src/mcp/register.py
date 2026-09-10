"""把内部 Tool Registry 挂到 FastMCP（不接第三方 CLI 命令）。

职责：
    为 ``dingda-mcp`` stdio 入口注册全部已登记 Tool（search / product / compare）。
"""

from __future__ import annotations

import inspect
import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from src.agent.core.compress import compress_tool_payload
from src.tools.registry import ToolSpec, call_tool, list_tools

logger = logging.getLogger("dingda.mcp.register")


def _allowed_tool_names() -> set[str] | None:
    """``DINGDA_MCP_TOOLS`` 白名单（逗号分隔）；未设则不过滤。"""
    raw = (os.getenv("DINGDA_MCP_TOOLS") or "").strip()
    if not raw:
        return None
    return {name.strip() for name in raw.split(",") if name.strip()}


def register_internal_tools(mcp: FastMCP) -> list[str]:
    """注册 Tool；``DINGDA_MCP_TOOLS`` 有值时只注册白名单内的，返回已注册名。

    没有白名单时（父 agent）跳过 ``internal_only`` 的工具 —— 那些只给特定子 agent。
    """
    allowed = _allowed_tool_names()
    registered: list[str] = []
    for spec in list_tools():
        if allowed is not None:
            if spec.name not in allowed:
                continue
        elif spec.internal_only:
            continue
        _bind(mcp, spec)
        registered.append(spec.name)
    logger.info(
        "mcp tools registered=%s allowlist=%s",
        registered,
        sorted(allowed) if allowed is not None else "全部（除内部工具）",
    )
    return registered


def _bind(mcp: FastMCP, spec: ToolSpec) -> None:
    async def handler(**kwargs: Any) -> dict[str, Any]:
        out = await call_tool(spec.name, kwargs)
        if isinstance(out, BaseModel):
            payload = out.model_dump()
        else:
            payload = dict(out)
        return compress_tool_payload(payload, tool_name=spec.name)

    handler.__name__ = spec.name
    handler.__doc__ = spec.description
    handler.__signature__ = _signature_from_model(spec.input_model)  # type: ignore[attr-defined]
    mcp.tool(name=spec.name, description=spec.description)(handler)


def _signature_from_model(model: type[BaseModel]) -> inspect.Signature:
    """用 Pydantic 字段生成 FastMCP 可识别的函数签名。"""
    params: list[inspect.Parameter] = []
    for name, field in model.model_fields.items():
        default: Any = inspect.Parameter.empty
        if not field.is_required():
            if field.default is not PydanticUndefined:
                default = field.default
            elif field.default_factory is not None:
                default = None
            else:
                default = None
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=field.annotation or Any,
            )
        )
    return inspect.Signature(params, return_annotation=dict[str, Any])
