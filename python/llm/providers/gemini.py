"""Google Gemini Provider。

调用 Gemini generateContent HTTP API，映射统一 ChatRequest/Response。"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config.models import ProviderSettings
from llm.models import ChatRequest, ChatResponse, LlmError

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


class GeminiProvider:
    def __init__(self, settings: ProviderSettings) -> None:
        self.settings = settings

    @property
    def kind(self) -> str:
        return "gemini"

    @property
    def supports_tools(self) -> bool:
        return False

    def _endpoint(self, model: str) -> str:
        base = self.settings.base_url.strip().rstrip("/") or DEFAULT_BASE_URL
        return f"{base}/v1beta/models/{model}:generateContent"

    def complete(self, request: ChatRequest) -> ChatResponse:
        model = request.model or self.settings.model
        system = "\n".join(m.content for m in request.messages if m.role == "system")
        contents = [
            {
                "role": "model" if m.role == "assistant" else "user",
                "parts": [{"text": m.content}],
            }
            for m in request.messages
            if m.role != "system"
        ]
        payload: dict[str, object] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        query = urlencode({"key": self.settings.api_key})
        url = f"{self._endpoint(model)}?{query}"
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=120) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise LlmError(f"gemini http {error.code}") from error
        except URLError as error:
            raise LlmError(f"gemini transport: {error}") from error

        candidates = data.get("candidates") or []
        if not candidates:
            raise LlmError("empty response")
        parts = candidates[0].get("content", {}).get("parts") or []
        reply = ""
        for part in parts:
            if part.get("text"):
                reply = str(part["text"]).strip()
                break
        if not reply:
            raise LlmError("empty response")
        finish = candidates[0].get("finishReason")
        return ChatResponse(reply=reply, finish_reason=str(finish) if finish else None)
