"""知识库业务服务 — 委托 knowledge 层。"""

from __future__ import annotations

from knowledge import ItemKnowledge, KnowledgeService, build_item_context

_service = KnowledgeService()


def item_context(item: ItemKnowledge) -> str:
    return _service.item_context(item)


def retrieve(query_vector: list[float], *, top_k: int = 5) -> list[str]:
    return _service.retrieve_text(query_vector, top_k=top_k)


__all__ = ["ItemKnowledge", "KnowledgeService", "build_item_context", "item_context", "retrieve"]
