"""通义千问 — DashScope 兼容模式（OpenAI 协议）。

复用 OpenAiCompatibleProvider，指向 DashScope 兼容 endpoint。"""

from llm.providers.openai import QwenProvider

__all__ = ["QwenProvider"]
