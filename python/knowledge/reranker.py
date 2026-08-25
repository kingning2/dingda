"""重排 — MVP 直接返回输入顺序。"""

from __future__ import annotations


def rerank(_query: str, candidates: list[str], *, top_k: int = 5) -> list[str]:
    return candidates[:top_k]
