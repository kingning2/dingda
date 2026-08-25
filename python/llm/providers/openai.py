"""OpenAI 兼容 Provider — DeepSeek / Qwen / Doubao / Ollama 等。

规范化 base_url，用 ``/v1/chat/completions`` 风格路径发 chat 请求。"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.models import ProviderSettings
from llm.models import ChatRequest, ChatResponse, LlmError

DEFAULT_CHAT_PATH = "/chat/completions"


def normalize_base_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if not base:
        return "https://api.openai.com/v1"
    if base.endswith(DEFAULT_CHAT_PATH):
        base = base[: -len(DEFAULT_CHAT_PATH)]
    if base.endswith("/v1") or base.endswith("/v2") or base.endswith("/v3"):
        return base
    return f"{base}/v1"


class OpenAiCompatibleProvider:
    def __init__(self, settings: ProviderSettings) -> None:
        self.settings = settings

    @property
    def kind(self) -> str:
        return "openai_compatible"

    @property
    def supports_tools(self) -> bool:
        return True

    def complete(self, request: ChatRequest) -> ChatResponse:
        base = normalize_base_url(self.settings.base_url)
        url = f"{base}{DEFAULT_CHAT_PATH}"
        model = request.model or self.settings.model
        is_official = "api.openai.com" in base

        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
        }
        if is_official:
            payload["max_completion_tokens"] = request.max_tokens
        else:
            payload["max_tokens"] = request.max_tokens
        if request.disable_thinking:
            payload["thinking"] = {"type": "disabled"}

        body = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.api_key}",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=120) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise LlmError(f"openai_compatible http {error.code}: {detail}") from error
        except URLError as error:
            raise LlmError(f"openai_compatible transport: {error}") from error

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content")
        if content is None:
            raise LlmError("empty response")
        reply = str(content).strip()
        if not reply:
            raise LlmError("empty response")
        finish = choice.get("finish_reason")
        return ChatResponse(reply=reply, finish_reason=str(finish) if finish else None)


# 别名：DeepSeek / Qwen 兼容模式均走 OpenAI 协议
DeepSeekProvider = OpenAiCompatibleProvider
QwenProvider = OpenAiCompatibleProvider
