"""LangGraph 编排包 — AI 能力（llm / knowledge / prompt）与 workflows。

两条工作流（经 ``__getattr__`` 延迟导出）::

    run_price_compare / run_reply
        比价图：web_research → article_analyze → planner → crawl
                → normalize → match → analyze → finalize
        定义见 ``agent.workflows.price_compare``

    run_buyer_reply
        买家 IM 条件图：guard → (generate | END)
        定义见 ``agent.workflows.buyer_reply``

能力子包：``agent.llm``、``agent.knowledge``、``agent.prompts``（模板 only）。
"""

from __future__ import annotations

from typing import Any

__all__ = ["run_buyer_reply", "run_price_compare", "run_reply"]


def __getattr__(name: str) -> Any:
    if name == "run_reply":
        from dingda_sidecar.agent.workflows.price_compare import run_reply

        return run_reply
    if name == "run_price_compare":
        from dingda_sidecar.agent.workflows.price_compare import run_price_compare

        return run_price_compare
    if name == "run_buyer_reply":
        from dingda_sidecar.agent.workflows.buyer_reply import run_buyer_reply

        return run_buyer_reply
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
