"""统一 LLM 客户端。

按 ProviderSettings 创建具体 Provider，对外提供 chat 等一致调用面。"""

from __future__ import annotations

from config.models import ProviderSettings
from llm.factory import create_provider
from llm.models import ChatMessage, ChatRequest, ChatResponse, LlmError
from llm.providers.base import LlmProvider


class LlmClient:
    """按 ProviderSettings 构造的统一 LLM 入口。"""

    def __init__(self, settings: ProviderSettings) -> None:
        self.settings = settings
        self._provider: LlmProvider = create_provider(settings)

    @property
    def kind(self) -> str:
        return self._provider.kind

    def chat(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        request = ChatRequest(
            model=self.settings.model,
            messages=[
                ChatMessage.system(system),
                ChatMessage.user(user),
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self.complete(request).reply

    def complete(self, request: ChatRequest) -> ChatResponse:
        try:
            return self._provider.complete(request)
        except LlmError:
            raise
        except Exception as error:
            raise LlmError(str(error)) from error

    @classmethod
    def from_openai_compat(cls, base_url: str, api_key: str, model: str) -> LlmClient:
        """兼容旧 `/v1/agent/reply` 仅传 base_url 的场景。"""
        return cls(
            ProviderSettings(
                provider_type="openai_compatible",
                api_key=api_key,
                base_url=base_url,
                model=model,
            ),
        )
