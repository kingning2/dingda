"""LLM 客户端：LangChain ``ChatOpenAI`` 门面。

职责：
    按 ``LlmSettings`` 建 OpenAI 兼容的 Chat 模型（DeepSeek / 豆包同口），
    对外保留 ``chat`` / ``list_models`` / ``from_env``，给凭据探活与发动机共用。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from core.errors import AppError

from agent.compress import compress_messages

from agent.llm.errors import to_app_error
from agent.llm.models import ChatResult, LlmSettings, usage_from
from agent.llm.providers import resolve_settings
from agent.llm.providers.doubao import EXTRA_BODY as DOUBAO_EXTRA_BODY

__all__ = ["LlmClient", "create_chat_model"]

Message = dict[str, Any]


def create_chat_model(
    settings: LlmSettings,
    *,
    model: str | None = None,
    http_async_client: httpx.AsyncClient | None = None,
    **overrides: Any,
) -> ChatOpenAI:
    """按配置建 LangChain ``ChatOpenAI``（OpenAI 兼容口）。"""
    kwargs: dict[str, Any] = {
        "model": (model or "").strip() or settings.model,
        "api_key": settings.api_key,
        "base_url": settings.base_url,
        "timeout": settings.timeout_s,
        "max_retries": settings.max_retries,
        "streaming": True,
    }
    if settings.provider_id == "doubao":
        kwargs["extra_body"] = dict(DOUBAO_EXTRA_BODY)
    if http_async_client is not None:
        kwargs["http_async_client"] = http_async_client
    kwargs.update(overrides)
    return ChatOpenAI(**kwargs)


class LlmClient:
    """门面：持有 Chat 模型 + 原生 OpenAI 客户端（拉模型列表）。"""

    def __init__(
        self,
        settings: LlmSettings,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        """``http`` 只在测试里注；注入的客户端不归本对象所有，``aclose`` 不关它。"""
        self._settings = settings
        self._owns_http = http is None
        self._http = http
        self._chat = create_chat_model(settings, http_async_client=http)
        self._openai = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.timeout_s,
            max_retries=settings.max_retries,
            http_client=http,
        )

    @property
    def settings(self) -> LlmSettings:
        """本客户端生效的配置。"""
        return self._settings

    @property
    def chat_model(self) -> ChatOpenAI:
        """LangChain Chat 模型（发动机 bind_tools / astream 用这个）。"""
        return self._chat

    @classmethod
    def from_env(
        cls,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> LlmClient:
        """从「显式入参 → 环境变量 → 供应商默认」解析配置并建好客户端。"""
        return cls(resolve_settings(provider=provider, model=model, base_url=base_url, api_key=api_key))

    def bound(self, *, model: str | None = None, **overrides: Any) -> ChatOpenAI:
        """覆盖模型名等参数后的新 Chat 实例（不改本客户端默认）。"""
        return create_chat_model(
            self._settings,
            model=model,
            http_async_client=self._http,
            **overrides,
        )

    async def chat(
        self,
        messages: Sequence[Message | BaseMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        compress: bool = True,
    ) -> ChatResult:
        """非流式说一次话（凭据探活）。"""
        effective = (model or "").strip() or self._settings.model
        prepared = _to_lc_messages(messages)
        if compress:
            prepared = _compress_lc(prepared, model=effective)

        llm = self.bound(model=effective, streaming=False)
        if temperature is not None:
            llm = llm.bind(temperature=temperature)
        if max_tokens is not None:
            llm = llm.bind(max_tokens=max_tokens)

        try:
            result = await llm.ainvoke(prepared)
        except Exception as exc:  # noqa: BLE001
            raise to_app_error(exc) from exc

        if not isinstance(result, AIMessage):
            raise AppError("llm.response_invalid", "上游返回不是 AIMessage", status_code=502)

        text = _text_of(result)
        reasoning = _reasoning_of(result)
        usage_meta = (result.usage_metadata or {}) if hasattr(result, "usage_metadata") else {}
        return ChatResult(
            text=text,
            reasoning=reasoning,
            finish_reason=str((result.response_metadata or {}).get("finish_reason") or "") or None,
            model=str((result.response_metadata or {}).get("model_name") or "") or effective,
            usage=usage_from(
                {
                    "prompt_tokens": usage_meta.get("input_tokens") or 0,
                    "completion_tokens": usage_meta.get("output_tokens") or 0,
                    "total_tokens": usage_meta.get("total_tokens") or 0,
                }
            )
            if usage_meta
            else None,
        )

    async def list_models(self) -> list[str]:
        """列出可用模型 id；不支持时抛 ``llm.models_unsupported``。"""
        from agent.llm.providers import get_provider

        entry = get_provider(self._settings.provider_id)
        if not entry.supports_models:
            raise AppError(
                "llm.models_unsupported",
                f"{entry.name} 不提供模型列表，请手动填写推理接入点 ID",
                status_code=400,
            )
        try:
            page = await self._openai.models.list()
        except Exception as exc:  # noqa: BLE001
            raise to_app_error(exc) from exc
        return sorted({item.id for item in page.data if getattr(item, "id", None)})

    async def aclose(self) -> None:
        """释放连接池。"""
        await self._openai.close()
        if self._owns_http and self._http is not None:
            await self._http.aclose()

    async def __aenter__(self) -> LlmClient:
        """``async with LlmClient.from_env() as client:``"""
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """退出时释放连接池。"""
        await self.aclose()


def _to_lc_messages(messages: Sequence[Message | BaseMessage]) -> list[BaseMessage]:
    """dict / BaseMessage → LangChain 消息列表。"""
    out: list[BaseMessage] = []
    for item in messages:
        if isinstance(item, BaseMessage):
            out.append(item)
            continue
        role = str(item.get("role") or "")
        content = item.get("content")
        text = "" if content is None else str(content)
        if role == "system":
            out.append(SystemMessage(content=text))
        elif role == "assistant":
            out.append(AIMessage(content=text))
        else:
            out.append(HumanMessage(content=text))
    return out


def _compress_lc(messages: list[BaseMessage], *, model: str) -> list[BaseMessage]:
    """经 ``compress_messages`` 压一轮，再转回 LC 消息。"""
    as_dicts: list[dict[str, Any]] = []
    for message in messages:
        if isinstance(message, SystemMessage):
            as_dicts.append({"role": "system", "content": message.content})
        elif isinstance(message, AIMessage):
            as_dicts.append({"role": "assistant", "content": message.content})
        else:
            as_dicts.append({"role": "user", "content": getattr(message, "content", "")})
    compressed = list(compress_messages(as_dicts, model=model))
    return _to_lc_messages(compressed)


def _text_of(message: AIMessage) -> str:
    """AIMessage.content → 纯文本。"""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return str(content or "")


def _reasoning_of(message: AIMessage) -> str | None:
    """从 additional_kwargs / response_metadata 挖思考内容。"""
    for bag in (message.additional_kwargs, message.response_metadata):
        if not isinstance(bag, dict):
            continue
        for key in ("reasoning_content", "reasoning"):
            value = bag.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None
