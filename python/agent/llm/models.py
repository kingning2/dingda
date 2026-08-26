"""LLM 包内共享类型 — Embedding 与错误。

Chat 走 LangChain 消息类型，不再维护自研 ChatRequest。"""

from __future__ import annotations

from dataclasses import dataclass, field


class LlmError(Exception):
    """LLM / Embedding 调用错误。"""


@dataclass
class EmbeddingRequest:
    model: str
    texts: list[str]


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]] = field(default_factory=list)
