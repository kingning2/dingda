"""LangGraph 图构建辅助。

``bind_context`` 把 GraphContext 闭包进节点函数，便于 ``StateGraph`` 编译。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from graph.core.context import GraphContext

NodeFn = Callable[[Mapping[str, Any], GraphContext], dict[str, Any]]


def bind_context(ctx: GraphContext, fn: NodeFn) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """将 GraphContext 绑定到节点函数。

    注意：包装函数的 ``state`` 参数不要注解成具体 TypedDict（如 GraphState）。
    LangGraph 1.x 会按注解类型裁剪注入的 channel，导致 BuyerReplyState 等字段丢失。
    """

    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        return fn(state, ctx)

    return wrapped
