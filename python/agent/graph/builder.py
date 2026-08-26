"""LangGraph 图构建辅助。

``bind_context(ctx, fn, step=...)``：注入 ``GraphContext``，并在节点进/出时
调用 ``ctx.step``，便于日志与 ``/v1/runtime/status`` 的 active_ops.stage。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from agent.graph.context import GraphContext

NodeFn = Callable[[Mapping[str, Any], GraphContext], dict[str, Any]]


def bind_context(
    ctx: GraphContext,
    fn: NodeFn,
    *,
    step: str | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """将 GraphContext 绑定到节点；``step`` 非空时上报 running/done/error。

    注意：包装函数的 ``state`` 不要注解成具体 TypedDict（如 GraphState）。
    LangGraph 1.x 会按注解类型裁剪 channel，导致 BuyerReplyState 等字段丢失。
    """

    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        if step:
            ctx.step(step, "running")
        try:
            result = fn(state, ctx)
        except Exception:
            if step:
                ctx.step(step, "error")
            raise
        if step:
            ctx.step(step, "done")
        return result

    return wrapped
