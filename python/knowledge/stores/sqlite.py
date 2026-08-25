"""内存向量存储 — MVP 骨架（非真实 SQLite 持久化）。

用余弦相似度做 top-k 检索，验证知识链路后再换持久后端。"""

from __future__ import annotations

import math


class SqliteVectorStore:
    """进程内简易向量库（后续可换 SQLite + vec）。"""

    def __init__(self) -> None:
        self._rows: list[tuple[str, str, list[float]]] = []

    def upsert(self, doc_id: str, chunks: list[str], vectors: list[list[float]]) -> None:
        self._rows = [(doc_id, chunk, vec) for chunk, vec in zip(chunks, vectors, strict=False)]

    def search(self, query_vector: list[float], *, top_k: int = 5) -> list[str]:
        scored = [(self._cosine(query_vector, vec), chunk) for _, chunk, vec in self._rows if vec]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
