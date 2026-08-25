"""Provider 协议。"""

from __future__ import annotations

from typing import Protocol

from llm.models import ChatRequest, ChatResponse


class LlmProvider(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def supports_tools(self) -> bool: ...

    def complete(self, request: ChatRequest) -> ChatResponse: ...
