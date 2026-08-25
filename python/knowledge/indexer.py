"""建索引 — 将文本块写入向量 store。

MVP 委托 ``SqliteVectorStore``（内存实现），后续可切换 Qdrant。"""

from __future__ import annotations

from knowledge.stores.sqlite import SqliteVectorStore


class Indexer:
    def __init__(self, store: SqliteVectorStore | None = None) -> None:
        self.store = store or SqliteVectorStore()

    def index(self, doc_id: str, chunks: list[str], vectors: list[list[float]]) -> None:
        self.store.upsert(doc_id, chunks, vectors)
