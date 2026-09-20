"""把 LangChain / OpenAI SDK 异常收成 ``AppError``。"""

from __future__ import annotations

import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, RateLimitError
from core.errors import AppError

logger = logging.getLogger("dingda.agent.llm.errors")


def to_app_error(exc: BaseException) -> AppError:
    """任意上游异常 → ``AppError``（已是则原样返回）。"""
    if isinstance(exc, AppError):
        return exc
    if isinstance(exc, AuthenticationError):
        return AppError("llm.auth_failed", "API key 无效或已过期", status_code=401)
    if isinstance(exc, RateLimitError):
        return AppError("llm.rate_limited", "模型供应商限流，稍后重试", status_code=429)
    if isinstance(exc, APITimeoutError):
        return AppError("llm.timeout", "模型响应超时，可以重试", status_code=504)
    if isinstance(exc, APIConnectionError):
        return AppError("llm.connection_failed", "连不上模型供应商，检查网络或 base_url", status_code=502)
    if isinstance(exc, APIStatusError):
        return _status_error(exc.status_code, _status_message(exc))
    logger.exception("LLM 调用意外异常")
    return AppError("llm.failed", str(exc) or type(exc).__name__, status_code=500)


def _status_message(exc: APIStatusError) -> str:
    """从 SDK 状态异常挖一句人话。"""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if body.get("message"):
            return str(body["message"])
    return str(exc) or f"上游返回 HTTP {exc.status_code}"


def _status_error(status: int, message: str) -> AppError:
    """HTTP 状态码 → ``AppError``。"""
    if status == 401:
        return AppError("llm.auth_failed", "API key 无效或已过期", status_code=401)
    if status == 403:
        return AppError("llm.permission_denied", "API key 无权调用该模型", status_code=403)
    if status == 404:
        return AppError(
            "llm.not_found",
            "模型或路径不存在：豆包要填推理接入点 ID（ep-...），base_url 也别漏了 /api/v3",
            status_code=404,
        )
    if status in {400, 422}:
        return AppError("llm.bad_request", message, status_code=400)
    if status == 429:
        return AppError("llm.rate_limited", "模型供应商限流，稍后重试", status_code=429)
    if status >= 500:
        return AppError("llm.upstream_error", message, status_code=502)
    return AppError("llm.failed", message, status_code=500)
