"""建索引 — 委托 store。"""

from __future__ import annotations

from knowledge.stores.sqlite import SqliteVectorStore


class Indexer:
    def __init__(self, store: SqliteVectorStore | None = None) -> None:
        self.store = store or SqliteVectorStore()

    def index(self, doc_id: str, chunks: list[str], vectors: list[list[float]]) -> None:
        self.store.upsert(doc_id, chunks, vectors)
