"""商品知识 — 对齐 Rust ``ItemKnowledge``。

组装商品上下文短摘要，并提供简单知识服务门面。"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class ItemKnowledge:
    title: str = ""
    price: float | None = None
    desc: str = ""
    ai_prompt: str = ""

    def to_context(self) -> str:
        title = self.title.strip() or "未知"
        price = str(self.price) if self.price is not None else "未知"
        lines = [
            f"商品标题: {_shorten(title, 120)}",
            f"商品价格: {price}元",
            f"商品描述: {_extract_readable_desc(self.desc)}",
        ]
        if self.ai_prompt.strip():
            lines.append(f"商品特殊说明: {_shorten(self.ai_prompt.strip(), 400)}")
        return "\n".join(lines)


def build_item_context(item: ItemKnowledge) -> str:
    return item.to_context()


class KnowledgeService:
    """知识库统一入口 — 商品上下文 + 检索编排。"""

    def __init__(self) -> None:
        from dingda_sidecar.agent.knowledge.indexer import Indexer
        from dingda_sidecar.agent.knowledge.retriever import Retriever

        self.indexer = Indexer()
        self.retriever = Retriever()

    def item_context(self, item: ItemKnowledge) -> str:
        return build_item_context(item)

    def retrieve_text(self, query_vector: list[float], *, top_k: int = 5) -> list[str]:
        from dingda_sidecar.agent.knowledge.reranker import rerank

        hits = self.retriever.retrieve(query_vector, top_k=top_k)
        return rerank("", hits, top_k=top_k)


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _extract_readable_desc(desc: str) -> str:
    text = desc.strip()
    if not text:
        return "暂无商品描述"
    if text.startswith("{") or text.startswith("["):
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return _shorten(text, 800)
        for key in ("description", "desc", "item_description", "itemDesc", "content"):
            raw = value.get(key) if isinstance(value, dict) else None
            if isinstance(raw, str) and raw.strip() and not raw.strip().startswith("{"):
                return _shorten(raw.strip(), 800)
        if isinstance(value, dict):
            detail = value.get("detail_params")
            if isinstance(detail, dict):
                parts = [detail.get(k) for k in ("title", "postInfo")]
                joined = "，".join(str(p) for p in parts if p)
                if joined:
                    return _shorten(joined, 800)
        return "暂无商品描述"
    return _shorten(text, 800)
