"""1688 官方找货网关 HTTP 客户端。

职责：
    签名注入、重试、错误映射；对外提供 find_product 与凭据探活 probe_credentials。
    供 crawler/sources/ali1688 与账号域调用，不暴露给 Tool。

设计说明：
    - Base: https://gateway.1688.com
    - API: /api/alibaba.1688.find.product/1.0.0/{channel}
    - channel 默认 dingda，可用 ALI_1688_CHANNEL 覆盖
    - **非 200 也可能带一个完整的业务错误体**（实测 AppKeyExpired = HTTP 400 + JSON），
      所以先解析响应体、先按错误码分流，最后才看状态码 —— 反过来会把真正的理由丢掉
    - probe_credentials 是三态（好 / 明确被拒 / 没问到）：判「凭据失效」只认那几条
      明确指向凭据的错误码，网络抖动不许把用户打成「请重新扫码」

使用示例：
    items = find_product({"query": "卫衣", "pageSize": 10})
    ok = probe_credentials()
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from functools import wraps
from typing import Any, Callable, Final, TypeVar

import requests

from channels.ali1688.ak import raw_ak
from channels.ali1688.sign import CLIENT_VERSION, build_auth_headers
from core.errors import AppError, rate_limited_error, sign_error

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

# AppKey（AK）失效的一族，语义是「这个凭据别用了，重试无用」。按**前缀**收而不是
# 逐个列举：这一族在网关侧还会长出新码，而漏掉一个的代价是主编排把它当成可重试的
# 网络抖动，反复换词重试。实测网关回的是 ``AppKeyExpired``。
_AK_CODE_PREFIXES = ("AppKey", "appKey")

# 探活：网关**明确拒绝**这套凭据的错误码。三条都指向凭据本身，重试与换词都无用。
_CREDENTIAL_REJECTED = frozenset(
    {
        "channel.ali1688_auth",
        "channel.ali1688_ak_missing",
        "channel.sign_failed",
    }
)

# 探活：压根没问到答案的错误码 —— 网络不通、被限流、网关自己 5xx。
# 既不能说凭据是好的，也不能说它是坏的。
_CREDENTIAL_UNANSWERED = frozenset(
    {
        "channel.ali1688_network",
        "channel.ali1688_gateway",
        "channel.rate_limited",
    }
)

# 探活的请求体。问的是凭据不是搜索结果，给个最小形状就够。
_PROBE_BODY: Final[dict[str, Any]] = {"query": "卫衣", "pageSize": 1}

# 探活结论的保鲜期。前端账号页每 30s 拉一次列表，不缓存就是拿找货接口当心跳打；
# 键是 AK 原文 —— 换了 AK 自然换键，旧结论不会粘在新凭据上。
_PROBE_TTL_S = 300.0
_PROBE_TIMEOUT_S = 6
_probe_cache: dict[str, tuple[float, bool]] = {}

T = TypeVar("T")


class _RetriableHTTPError(Exception):
    """可重试的网关 HTTP 错误。"""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


def _with_retry(func: Callable[..., T]) -> Callable[..., T]:
    """网络与 5xx 指数退避重试。

    可传 ``_retries=N`` 指定这一次的尝试次数。它由装饰器摘掉，里层函数看不到，
    所以 ``api_post`` 的签名不受影响。探活只试一次 —— 它站在账号列表的调用路径上，
    不该让用户为了看一眼账号页蹲三轮退避。
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        retries = max(1, int(kwargs.pop("_retries", MAX_RETRIES)))
        last: Exception | None = None
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                last = exc
                delay = min(RETRY_DELAY_BASE * (2**attempt), 10)
                logger.warning(
                    "网络异常 attempt=%s/%s delay=%ss err=%s",
                    attempt + 1,
                    retries,
                    delay,
                    exc,
                )
                if attempt < retries - 1:
                    time.sleep(delay)
            except _RetriableHTTPError as exc:
                last = exc
                delay = min(RETRY_DELAY_BASE * (2**attempt), 10)
                logger.warning(
                    "网关瞬态错误 attempt=%s/%s status=%s delay=%ss",
                    attempt + 1,
                    retries,
                    exc.status_code,
                    delay,
                )
                if attempt < retries - 1:
                    time.sleep(delay)
        raise AppError(
            "channel.ali1688_network",
            f"网络异常，已重试{retries}次: {last}",
            status_code=502,
        )

    return wrapper


def _is_ak_code(code: str) -> bool:
    """这个码是不是 AppKey 失效（重试无用）。"""
    return bool(code) and code.startswith(_AK_CODE_PREFIXES)


def _handle_biz_error(result: dict[str, Any]) -> None:
    """网关的业务失败 → AppError。

    ``result`` 既可能是 HTTP 200 的回执，也可能是非 200 带的 JSON 错误体 ——
    网关两种形状用的是同一套 ``code`` / ``msgCode``，所以进来之前不要先按状态码分流。
    """
    msg_code = str(result.get("msgCode") or "")
    code = str(result.get("code") or "")
    # 说明字段两种形状不一样：老回执用 ``msgInfo``，实测 AppKeyExpired 用 ``message``。
    # 漏读 ``message`` 的话，唯一说明问题的那句话就又没了。
    msg_info = result.get("msgInfo") or result.get("message")

    if _is_ak_code(msg_code) or _is_ak_code(code):
        raise AppError(
            "channel.ali1688_auth",
            f"{msg_info or 'AppKey 无效'}（1688 AppKey 已失效，重试无用，需重新签发）",
            status_code=401,
        )
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


def _json_body(resp: requests.Response) -> dict[str, Any] | None:
    """尽量把响应体解成 dict；不是 JSON（网关 5xx 可能回 HTML）或不是对象就 None。"""
    try:
        body = resp.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _is_error_envelope(result: dict[str, Any] | None, status_code: int) -> bool:
    """响应体是不是网关的错误信封。

    HTTP 200 时只认显式的 ``success: false`` —— 正常回执里也可能带一个 ``code``
    字段，拿它当判据会把成功响应当失败。非 200 时才认 ``code`` / ``msgCode``：
    网关的错误回执一定带其中之一，而纯 HTTP 层的故障解不出来，那时该报的是状态码。
    """
    if result is None:
        return False
    if result.get("success") is False:
        return True
    return status_code != 200 and bool(result.get("code") or result.get("msgCode"))


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

    # **先解析、先分流业务错误，再看状态码。** 网关常用非 200 回执带一个完整的
    # JSON 错误体（实测 AppKeyExpired 就是 HTTP 400 + ``{"code":"AppKeyExpired",
    # "message":"appKey expired"}``）。反过来写 —— 先 ``status_code != 200`` 就抛 ——
    # 会把唯一说明问题的那句话丢掉，只剩一句「网关异常（HTTP 400）」：用户不知道
    # 发生了什么，主编排还会把它当成可重试的临时故障去反复换词重试。
    result = _json_body(resp)
    if _is_error_envelope(result, resp.status_code) and result is not None:
        _handle_biz_error(result)

    if resp.status_code != 200:
        raise AppError(
            "channel.ali1688_gateway",
            f"网关异常（HTTP {resp.status_code}）",
            status_code=502,
        )
    if result is None:
        raise AppError("channel.ali1688_format", "API 返回结构异常", status_code=502)

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


def probe_credentials(*, timeout: int = _PROBE_TIMEOUT_S) -> bool | None:
    """打一次网关，问「这套 AK 现在还被认吗」。

    三态，**不要缩成 bool**：

    - ``True``  网关收下了这次调用（哪怕它嫌请求参数不对）—— 凭据是好的
    - ``False`` 网关明确拒了这套凭据（auth / 签名 / 没配 AK）—— 重试无用
    - ``None``  没问到答案（网络不通、限流、网关 5xx）—— **不敢当成失效**

    第三态是这件事的重点。账号列表把 ``False`` 渲染成「登录已过期，请重新扫码」，
    拿一次网络抖动换用户白扫一次码，比多显示一会儿「已登录」更糟。所以判据反过来
    写：只认 ``_CREDENTIAL_REJECTED`` 里那几条明确指向凭据的错误码，其余一律归到
    「没问到」—— 包括将来网关新长出来的、我们还不认识的码。

    请求体给最小形状即可：问的是凭据不是搜索结果，``ParamMissing`` 那种「网关收下
    了但嫌参数不对」恰恰要算作凭据过关。

    只试一次（``_retries=1``）并按 AK 缓存 ``_PROBE_TTL_S``：这是探活，不该让账号
    列表蹲三轮退避，也不该每 30s 打一次找货接口。
    """
    raw = raw_ak()
    if not raw:
        return False

    now = time.monotonic()
    cached = _probe_cache.get(raw)
    if cached and now < cached[0]:
        return cached[1]

    try:
        api_post(FIND_PRODUCT_API, dict(_PROBE_BODY), timeout=timeout, _retries=1)
    except AppError as exc:
        if exc.code in _CREDENTIAL_REJECTED:
            verdict: bool | None = False
        elif exc.code in _CREDENTIAL_UNANSWERED:
            verdict = None
        else:
            # 网关答了话，只是不满意这次请求 —— 凭据本身没问题。
            verdict = True
        logger.info("1688 探活 code=%s verdict=%s", exc.code, verdict)
    except Exception as exc:  # 探活绝不向外抛
        logger.info("1688 探活异常: %s", exc)
        verdict = None
    else:
        verdict = True

    # 「没问到」不缓存：下次接着问，一旦问到就立刻定下来。
    if verdict is not None:
        _probe_cache[raw] = (now + _PROBE_TTL_S, verdict)
    return verdict
