"""Provider 工厂 — 对齐 Rust `provider_from_settings` / `normalize_provider_type`。"""

from __future__ import annotations

from config.models import ProviderSettings
from llm.models import LlmError
from llm.providers.anthropic import AnthropicProvider
from llm.providers.base import LlmProvider
from llm.providers.dashscope_app import DashScopeAppProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.openai import OpenAiCompatibleProvider


def normalize_provider_type(provider_type: str, base_url: str, model: str) -> str:
    provider = provider_type.strip().lower().replace("-", "_")
    mapping = {
        "openai": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "openai兼容": "openai_compatible",
        "dashscope_compatible": "openai_compatible",
        "qwen": "openai_compatible",
        "dashscope": "openai_compatible",
        "deepseek": "openai_compatible",
        "doubao": "openai_compatible",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "gemini": "gemini",
        "google_gemini": "gemini",
        "dashscope_app": "dashscope_app",
        "dashscope应用": "dashscope_app",
    }
    normalized = mapping.get(provider, provider)
    if normalized in mapping.values():
        return normalized

    base = base_url.strip().lower()
    model_l = model.strip().lower()
    if "generativelanguage.googleapis.com" in base:
        return "gemini"
    if "api.anthropic.com" in base:
        return "anthropic"
    if "/apps/" in base:
        return "dashscope_app"
    if "gemini" in model_l:
        return "gemini"
    if "claude" in model_l:
        return "anthropic"
    return "openai_compatible"


def create_provider(settings: ProviderSettings) -> LlmProvider:
    kind = normalize_provider_type(settings.provider_type, settings.base_url, settings.model)
    resolved = ProviderSettings(
        provider_type=kind,
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
    )
    match kind:
        case "anthropic":
            return AnthropicProvider(resolved)
        case "gemini":
            return GeminiProvider(resolved)
        case "dashscope_app":
            return DashScopeAppProvider(resolved)
        case _:
            return OpenAiCompatibleProvider(resolved)

    raise LlmError(f"unsupported provider: {kind}")
