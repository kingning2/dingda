"""把内部 Tool Registry 挂到 FastMCP（不接第三方 CLI 命令）。

职责：
    为 ``dingda-mcp`` stdio 入口注册全部已登记 Tool（search / product / compare）。
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from src.agent.core.compress import compress_tool_payload
from src.tools.registry import ToolSpec, call_tool, list_tools

logger = logging.getLogger("dingda.mcp.register")


def register_internal_tools(mcp: FastMCP) -> list[str]:
    """注册 registry 中的全部 Tool；返回已注册名。"""
    registered: list[str] = []
    for spec in list_tools():
        _bind(mcp, spec)
        registered.append(spec.name)
        logger.info("mcp tool registered name=%s", spec.name)
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
