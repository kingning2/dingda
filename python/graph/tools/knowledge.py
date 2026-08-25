"""知识检索 Graph 工具。

向知识服务查询与当前商品/问题相关的片段，供 search / 回复节点引用。"""

from __future__ import annotations


def retrieve_knowledge(query: str) -> str:
    """MVP：返回空；后续接 embedding + retriever。"""
    del query
    return ""
