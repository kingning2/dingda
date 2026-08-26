"""向量检索 — 按 query embedding 查 store。

封装 top-k 查询，供 KnowledgeService / Graph 知识工具使用。"""

from __future__ import annotations

from agent.knowledge.stores.sqlite import SqliteVectorStore


class Retriever:
    def __init__(self, store: SqliteVectorStore | None = None) -> None:
        self.store = store or SqliteVectorStore()

    def retrieve(self, query_vector: list[float], *, top_k: int = 5) -> list[str]:
        return self.store.search(query_vector, top_k=top_k)
