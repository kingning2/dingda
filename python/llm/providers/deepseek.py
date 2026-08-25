"""DeepSeek Provider — 复用 OpenAI 兼容协议实现。

仅切换默认 base_url / 模型约定，请求编解码与 OpenAiCompatibleProvider 相同。"""

from llm.providers.openai import DeepSeekProvider

__all__ = ["DeepSeekProvider"]
