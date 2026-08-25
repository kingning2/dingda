"""重排 — MVP 直接返回输入顺序。

占位接口，便于后续接入交叉编码器而不改调用方。"""

from __future__ import annotations


def rerank(_query: str, candidates: list[str], *, top_k: int = 5) -> list[str]:
    return candidates[:top_k]
