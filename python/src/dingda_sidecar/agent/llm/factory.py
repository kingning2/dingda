"""Provider 类型归一 — 对齐 Rust ``normalize_provider_type``。

只做字符串规范化，不再实例化自研 Provider（模型由 LangChain ChatOpenAI 承担）。
"""

from __future__ import annotations


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
