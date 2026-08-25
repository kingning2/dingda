"""Graph 编排层错误类型。"""

from __future__ import annotations


class GraphError(Exception):
    """Graph 执行基础错误。"""


class NodeError(GraphError):
    """单个节点执行失败。"""

    def __init__(self, node: str, message: str) -> None:
        super().__init__(f"{node}: {message}")
        self.node = node
        self.message = message


class WorkflowError(GraphError):
    """工作流编译或调度失败。"""
