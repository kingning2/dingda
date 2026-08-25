"""DashScope App Provider — 百炼应用级接口。

面向已发布应用的 completion 调用，与普通 OpenAI 兼容 chat 路径区分。"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.models import ProviderSettings
from llm.models import ChatRequest, ChatResponse, LlmError

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/api/v1/apps"


class DashScopeAppProvider:
    def __init__(self, settings: ProviderSettings) -> None:
        self.settings = settings

    @property
    def kind(self) -> str:
        return "dashscope_app"

    @property
    def supports_tools(self) -> bool:
        return False

    def _app_id(self) -> str:
        base = self.settings.base_url.strip()
        marker = "/apps/"
        if marker in base:
            after = base.split(marker, 1)[1]
            app_id = after.split("/", 1)[0].strip()
            if app_id:
                return app_id
        model = self.settings.model.strip()
        if model:
            return model
        raise LlmError("dashscope_app: 基址或模型名中未找到 app_id")

    def _endpoint(self, app_id: str) -> str:
        return f"{DEFAULT_BASE_URL}/{app_id}/completion"

    def complete(self, request: ChatRequest) -> ChatResponse:
        app_id = self._app_id()
        system = "\n".join(m.content for m in request.messages if m.role == "system")
        user = "\n".join(m.content for m in request.messages if m.role == "user")
        if system and user:
            prompt = f"{system}\n\n用户问题：{user}\n\n请直接回答用户的问题："
        elif user:
            prompt = user
        else:
            prompt = system

        payload = {
            "input": {"prompt": prompt},
            "parameters": {
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            },
            "debug": {},
        }
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            self._endpoint(app_id),
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
            raise LlmError(f"dashscope_app http {error.code}") from error
        except URLError as error:
            raise LlmError(f"dashscope_app transport: {error}") from error

        text = data.get("output", {}).get("text")
        if not text or not str(text).strip():
            raise LlmError("empty response")
        return ChatResponse(reply=str(text).strip())
