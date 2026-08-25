"""Anthropic Claude Provider。

走 Messages API（含 API version 头），把统一 ChatRequest 映射为 Claude 请求。"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.models import ProviderSettings
from llm.models import ChatRequest, ChatResponse, LlmError

DEFAULT_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


class AnthropicProvider:
    def __init__(self, settings: ProviderSettings) -> None:
        self.settings = settings

    @property
    def kind(self) -> str:
        return "anthropic"

    @property
    def supports_tools(self) -> bool:
        return False

    def _endpoint(self) -> str:
        base = self.settings.base_url.strip().rstrip("/") or DEFAULT_BASE_URL
        return f"{base}/v1/messages"

    def complete(self, request: ChatRequest) -> ChatResponse:
        system = "\n".join(m.content for m in request.messages if m.role == "system")
        messages = [
            {"role": m.role, "content": m.content} for m in request.messages if m.role != "system"
        ]
        payload: dict[str, object] = {
            "model": request.model or self.settings.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        body = json.dumps(payload).encode("utf-8")
        req = Request(
            self._endpoint(),
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.settings.api_key,
                "anthropic-version": API_VERSION,
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=120) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise LlmError(f"anthropic http {error.code}") from error
        except URLError as error:
            raise LlmError(f"anthropic transport: {error}") from error

        parts = data.get("content") or []
        reply = ""
        for part in parts:
            if part.get("type") == "text" and part.get("text"):
                reply = str(part["text"]).strip()
                break
        if not reply:
            raise LlmError("empty response")
        finish = data.get("stop_reason")
        return ChatResponse(reply=reply, finish_reason=str(finish) if finish else None)
