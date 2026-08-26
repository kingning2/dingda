"""知识库业务服务 — 经 KnowledgeRuntime 取单例。"""

from __future__ import annotations

from agent.knowledge import ItemKnowledge, KnowledgeService, build_item_context
from runtimes.knowledge.runtime import get_knowledge_service


def item_context(item: ItemKnowledge) -> str:
    return get_knowledge_service().item_context(item)


def retrieve(query_vector: list[float], *, top_k: int = 5) -> list[str]:
    return get_knowledge_service().retrieve_text(query_vector, top_k=top_k)


__all__ = ["ItemKnowledge", "KnowledgeService", "build_item_context", "item_context", "retrieve"]
