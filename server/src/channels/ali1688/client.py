"""1688 官方找货网关 HTTP 客户端。

职责：
    签名注入、重试、错误映射；对外提供 find_product。
    供 crawler/sources/ali1688 调用，不暴露给 Tool。

设计说明：
    - Base: https://gateway.1688.com
    - API: /api/alibaba.1688.find.product/1.0.0/{channel}
    - channel 默认 dingda，可用 ALI_1688_CHANNEL 覆盖

使用示例：
    items = find_product({"query": "卫衣", "pageSize": 10})
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from functools import wraps
from typing import Any, Callable, TypeVar

import requests

from src.channels.ali1688.sign import CLIENT_VERSION, build_auth_headers
from src.shared.errors import AppError, rate_limited_error, sign_error

logger = logging.getLogger("dingda.channel.ali1688.client")

BASE_URL = "https://gateway.1688.com"
FIND_PRODUCT_API = "/api/alibaba.1688.find.product/1.0.0"
CHANNEL = os.environ.get("ALI_1688_CHANNEL", "dingda")
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1
RETRIABLE_STATUS = {500, 502, 503, 504}

_GATEWAY_AUTH_CODES = {
    "1688_token_expired",
    "1688_invalid_token",
    "1688_token_revoked",
    "1688_token_unauthorized",
    "1688_no_scope_specified",
    "1688_invalid_scope",
}

T = TypeVar("T")


class _RetriableHTTPError(Exception):
    """可重试的网关 HTTP 错误。"""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


def _with_retry(func: Callable[..., T]) -> Callable[..., T]:
    """网络与 5xx 指数退避重试。"""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        last: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                last = exc
                delay = min(RETRY_DELAY_BASE * (2**attempt), 10)
                logger.warning(
                    "网络异常 attempt=%s/%s delay=%ss err=%s",
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                    exc,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
            except _RetriableHTTPError as exc:
                last = exc
                delay = min(RETRY_DELAY_BASE * (2**attempt), 10)
                logger.warning(
                    "网关瞬态错误 attempt=%s/%s status=%s delay=%ss",
                    attempt + 1,
                    MAX_RETRIES,
                    exc.status_code,
                    delay,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(delay)
        raise AppError(
            "channel.ali1688_network",
            f"网络异常，已重试{MAX_RETRIES}次: {last}",
            status_code=502,
        )

    return wrapper


def _handle_biz_error(result: dict[str, Any]) -> None:
    """HTTP 200 但业务失败 → AppError。"""
    msg_code = str(result.get("msgCode") or "")
    code = str(result.get("code") or "")
    msg_info = result.get("msgInfo")

    if msg_code in _GATEWAY_AUTH_CODES:
        raise AppError(
            "channel.ali1688_auth",
            str(msg_info or f"授权错误：{msg_code}"),
            status_code=401,
        )
    if code == "SignatureInvalid":
        raise sign_error("签名校验失败")
    if code in ("ParamMissing", "APIUnsupported"):
        raise AppError("channel.ali1688_param", str(msg_info or code), status_code=400)
    if code in ("QosAppFrequencyLimit", "QosApiFrequencyLimit"):
        raise rate_limited_error("请求超限")
    if code in ("ISPInvokeError", "ISPInvokeTimeout"):
        raise AppError("channel.ali1688_upstream", str(msg_info or code), status_code=502)

    detail = msg_info or msg_code or "未知业务错误"
    raise AppError("channel.ali1688_failed", str(detail), status_code=502)


@_with_retry
def api_post(path: str, body: dict[str, Any] | None = None, *, timeout: int = 30) -> dict[str, Any]:
    """POST 1688 网关（自动签名 + 重试）。"""
    channel = CHANNEL
    full_path = f"{path}/{channel}"
    url = f"{BASE_URL}{full_path}"
    body_str = json.dumps(body or {}, ensure_ascii=False)

    headers = build_auth_headers("POST", full_path, body_str)
    if not headers:
        raise AppError(
            "channel.ali1688_ak_missing",
            "1688 AK 未配置。请设置环境变量 ALI_1688_AK，或写入 ~/.dingda/v2/ali1688/ak.json",
            status_code=401,
        )
    headers["x-skill-code"] = "dingda-ali1688"
    headers["x-skill-version"] = CLIENT_VERSION
    headers["x-request-id"] = uuid.uuid4().hex

    logger.info("api_post start path=%s", full_path)
    resp = requests.post(
        url,
        headers=headers,
        data=body_str.encode("utf-8"),
        timeout=timeout,
    )

    if resp.status_code in RETRIABLE_STATUS:
        raise _RetriableHTTPError(resp.status_code)
    if resp.status_code != 200:
        raise AppError(
            "channel.ali1688_gateway",
            f"网关异常（HTTP {resp.status_code}）",
            status_code=502,
        )

    result = resp.json()
    if result.get("success") is False:
        _handle_biz_error(result)

    model = result.get("model")
    if isinstance(model, dict):
        logger.info("api_post done via=model")
        return model
    data = result.get("data")
    if isinstance(data, dict):
        logger.info("api_post done via=data")
        return data
    raise AppError("channel.ali1688_format", "API 返回结构异常", status_code=502)


def find_product(request_body: dict[str, Any]) -> list[dict[str, Any]]:
    """调用找货 API，返回原始商品条目列表。"""
    logger.info("find_product start keys=%s", sorted(request_body.keys()))
    resp = api_post(FIND_PRODUCT_API, request_body)
    data = resp.get("data")
    if not isinstance(data, list):
        raise AppError("channel.ali1688_format", "格式异常，请稍后重试", status_code=502)
    logger.info("find_product done count=%s", len(data))
    return data
