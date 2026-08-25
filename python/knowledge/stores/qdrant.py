"""Qdrant 存储 — 骨架（尚未接入 SDK）。

预留与 SQLite 相同的 store 接口，便于后续替换向量后端。"""

from __future__ import annotations


class QdrantStore:
    def __init__(self, url: str = "http://127.0.0.1:6333", collection: str = "dingda") -> None:
        self.url = url
        self.collection = collection

    def upsert(self, doc_id: str, chunks: list[str], vectors: list[list[float]]) -> None:
        del doc_id, chunks, vectors
        raise NotImplementedError("Qdrant store 尚未接入 SDK")

    def search(self, query_vector: list[float], *, top_k: int = 5) -> list[str]:
        del query_vector, top_k
        raise NotImplementedError("Qdrant store 尚未接入 SDK")
