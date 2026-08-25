"""LLM Provider 配置模型。

定义 ProviderKind 与 ProviderSettings（api_key、base_url、model 等），供工厂与客户端使用。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderKind(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    DASHSCOPE_APP = "dashscope_app"


@dataclass(frozen=True)
class ProviderSettings:
    provider_type: str
    api_key: str
    base_url: str
    model: str

    @property
    def kind(self) -> ProviderKind:
        try:
            return ProviderKind(self.provider_type)
        except ValueError:
            return ProviderKind.OPENAI_COMPATIBLE
