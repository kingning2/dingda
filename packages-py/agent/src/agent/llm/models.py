"""LLM 契约：连接配置与探活出参（不依赖具体 SDK）。

职责：
    ``LlmSettings`` 是凭据解析结果；``ChatResult`` / ``Usage`` 给探活与日志用。
    发动机对话走 LangChain ``BaseMessage``，不再用本文件里的流式事件类型。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True, slots=True)
class LlmSettings:
    """一次调用要用的全部连接参数。由 ``providers.resolve_settings`` 产出。

    ``model`` 是**解析后**的模型名（豆包那边是 ``ep-`` 接入点 ID），不是配置里那串原始值。
    """

    provider_id: str
    base_url: str
    model: str
    api_key: str
    timeout_s: float = 60.0
    max_retries: int = 2


class Usage(BaseModel):
    """一次调用的 token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResult(BaseModel):
    """一次非流式调用的完整结果（凭据探活等）。"""

    text: str = Field(default="", description="正文")
    reasoning: str | None = Field(default=None, description="思考内容（若上游给）")
    finish_reason: str | None = Field(default=None, description="stop / tool_calls / length …")
    model: str = Field(default="", description="上游回显的模型名")
    usage: Usage | None = Field(default=None, description="token 用量，上游不给时为 None")


def usage_from(raw: Any) -> Usage | None:
    """上游 usage 对象 / dict → 本包的 ``Usage``；给 None 就还是 None。"""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return Usage(
            prompt_tokens=int(raw.get("prompt_tokens") or 0),
            completion_tokens=int(raw.get("completion_tokens") or 0),
            total_tokens=int(raw.get("total_tokens") or 0),
        )
    return Usage(
        prompt_tokens=int(getattr(raw, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(raw, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(raw, "total_tokens", 0) or 0),
    )
