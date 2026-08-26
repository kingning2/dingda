"""知识检索 LangChain 工具 — AI 可见描述与参数。"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.knowledge.retrieve import retrieve_knowledge


class KnowledgeRetrieveArgs(BaseModel):
    query: str = Field(description="要检索的问题或商品相关描述")


def _run_knowledge_retrieve(query: str) -> str:
    return retrieve_knowledge(query) or ""


def make_knowledge_retrieve_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_run_knowledge_retrieve,
        name="knowledge_retrieve",
        description=(
            "从本地商品/业务知识库检索相关短摘要。"
            "适合补充内部已知信息；公开网页请改用 web_fetch / web_scrape。"
        ),
        args_schema=KnowledgeRetrieveArgs,
    )


__all__ = ["KnowledgeRetrieveArgs", "make_knowledge_retrieve_tool"]
