"""Provider 协议（Protocol）。

规定 ``chat`` 等必须实现的方法，供 LlmClient 与工厂做结构化依赖。"""

from __future__ import annotations

from typing import Protocol

from llm.models import ChatRequest, ChatResponse


class LlmProvider(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def supports_tools(self) -> bool: ...

    def complete(self, request: ChatRequest) -> ChatResponse: ...
