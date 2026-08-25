"""LLM 消息与请求/响应模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


class LlmError(Exception):
    """LLM 调用错误。"""


@dataclass
class ChatMessage:
    role: str
    content: str = ""

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> ChatMessage:
        return cls(role="assistant", content=content)


@dataclass
class ChatRequest:
    model: str
    messages: list[ChatMessage]
    max_tokens: int = 1024
    temperature: float = 0.7
    disable_thinking: bool = True


@dataclass
class ChatResponse:
    reply: str
    finish_reason: str | None = None


@dataclass
class EmbeddingRequest:
    model: str
    texts: list[str]


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]] = field(default_factory=list)
