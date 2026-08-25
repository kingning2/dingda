"""兼容层 — 委托 ``graph.workflows.price_compare.run_reply``。

旧 sidecar agent 入口仍可从此模块导入比价回复函数。"""

from graph.workflows.price_compare import run_reply

__all__ = ["run_reply"]
