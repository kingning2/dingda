"""1688 网关错误映射单测：非 200 的业务错误体不能被丢掉。

真实故障（2026-09-18 实测）：AK 过期时网关回的是 **HTTP 400 + 一个完整的 JSON
错误体**（``{"code":"AppKeyExpired","message":"appKey expired"}``），而客户端先判
``status_code != 200`` 就抛，于是那句唯一说明问题的话被丢掉，用户只看到
「网关异常（HTTP 400）」，主编排还会把它当成可重试的网络抖动去反复换词重试。

这里钉住的就是这条：**理由与错误码都要活下来**。``requests.post`` 换成假响应，
不碰网络。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from channels.ali1688 import client as ali_client
from core.errors import AppError


class _Resp:
    """假响应：给状态码与响应体，``json()`` 的行为可关掉（模拟非 JSON 回执）。"""

    def __init__(self, status_code: int, body: Any = None, *, is_json: bool = True) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self._body = body
        self._is_json = is_json

    def json(self) -> Any:
        if not self._is_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._body


def _returns(resp: _Resp):
    """回固定响应的假 ``requests.post``（可直接当函数用，不套 ``with``）。"""

    def fake_post(*args: Any, **kwargs: Any) -> _Resp:
        return resp

    return fake_post


def _post_returning(resp: _Resp):
    """把 ``requests.post`` 换成回固定响应的假函数。"""
    return patch.object(ali_client.requests, "post", _returns(resp))


def _call(resp: _Resp) -> dict[str, Any]:
    """跑一次 ``api_post``；AK 头打掉（不依赖本机 ak.json），退避的 sleep 也打掉。"""
    with patch.object(ali_client, "build_auth_headers", lambda *a, **k: {"Content-Type": "application/json"}), \
         patch.object(ali_client.time, "sleep", lambda *_: None), \
         _post_returning(resp):
        return ali_client.api_post("/api/alibaba.1688.find.product/1.0.0", {"query": "卫衣"})


def _code_of(resp: _Resp) -> tuple[str, str]:
    """拿 ``(error_code, message)``。"""
    with pytest.raises(AppError) as info:
        _call(resp)
    return info.value.code, info.value.message


# 实测形状：traceId / codeType / requestId / timestamp 都照抄，只留断言用得到的。
_AK_EXPIRED = {
    "traceId": "215045bc17897068198703988e0b36",
    "code": "AppKeyExpired",
    "codeType": "ISV",
    "success": False,
    "requestId": "2107c143mtshbea3-19338",
    "message": "appKey expired",
    "timestamp": 1789706819879,
}


def test_non_200_with_business_body_keeps_the_reason() -> None:
    """【回归】HTTP 400 + AppKeyExpired：错误码与理由都必须活下来。

    改之前这里回的是 ``channel.ali1688_gateway`` / 「网关异常（HTTP 400）」——
    一个凭据失效被降级成无从下手的网关错误。
    """
    code, message = _code_of(_Resp(400, _AK_EXPIRED))

    assert code == "channel.ali1688_auth"
    assert "appKey expired" in message


def test_ak_error_codes_are_matched_by_prefix() -> None:
    """AppKey 这一族按前缀收 —— 网关侧还会长出新码，漏一个就会被当成可重试故障。"""
    for gateway_code in ("AppKeyExpired", "AppKeyInvalid", "AppKeyNotExist"):
        code, _ = _code_of(_Resp(400, {**_AK_EXPIRED, "code": gateway_code}))
        assert code == "channel.ali1688_auth", gateway_code


def test_non_200_without_json_falls_back_to_the_status_code() -> None:
    """非 200 且解析不出 JSON（网关 5xx 可能回 HTML）→ 报状态码，不编业务错误。"""
    code, _ = _code_of(_Resp(500, "<html>502 Bad Gateway</html>", is_json=False))

    # 500 在 RETRIABLE_STATUS 里，退避重试 3 次后归到网络错误
    assert code == "channel.ali1688_network"


def test_non_200_with_json_but_no_code_reports_the_status() -> None:
    """非 200 但没有错误码（不是业务错误信封）→ 报状态码。"""
    code, message = _code_of(_Resp(404, {"detail": "Not Found"}))

    assert code == "channel.ali1688_gateway"
    assert "404" in message


def test_http_200_with_success_false_still_maps_business_errors() -> None:
    """HTTP 200 + ``success: false`` 的老路径不能因为这次改动而失效。"""
    signature, _ = _code_of(_Resp(200, {"success": False, "code": "SignatureInvalid"}))
    assert signature == "channel.sign_failed"

    token, message = _code_of(
        _Resp(200, {"success": False, "msgCode": "1688_token_expired", "msgInfo": "令牌过期"})
    )
    assert token == "channel.ali1688_auth"
    assert "令牌过期" in message

    unknown, message = _code_of(
        _Resp(200, {"success": False, "code": "SomethingNew", "message": "新错误"})
    )
    assert unknown == "channel.ali1688_failed"
    assert "新错误" in message


def test_http_200_success_body_is_not_swallowed() -> None:
    """正常回执照样透传 —— ``code`` 字段不能把成功响应当成失败（上面那条的边界）。"""
    out = _call(_Resp(200, {"code": "Success", "model": {"data": [{"itemId": 1}]}}))

    assert out == {"data": [{"itemId": 1}]}


def test_http_200_with_unexpected_shape_reports_format() -> None:
    """200 但没有 model / data（或根本不是对象）→ 结构异常。"""
    code, _ = _code_of(_Resp(200, {"weird": True}))
    assert code == "channel.ali1688_format"

    code, _ = _code_of(_Resp(200, [1, 2, 3]))
    assert code == "channel.ali1688_format"


def test_missing_ak_is_reported_before_any_network_call() -> None:
    """AK 没配就直说，不发请求。"""
    with patch.object(ali_client, "build_auth_headers", lambda *a, **k: None):
        with pytest.raises(AppError) as info:
            ali_client.api_post("/api/alibaba.1688.find.product/1.0.0", {})

    assert info.value.code == "channel.ali1688_ak_missing"


# ---------------------------------------------------------------------------
# 凭据探活：``probe_credentials`` 的三态与代价
#
# 背景（2026-09-18）：账号列表原来只做本地字符串比对，AK 被网关吊销或过期时文件还在、
# 字符串也还是那一串，于是账号页一直显示「已登录」，一调就错。修法是在列表路径上真打
# 一次网关；但探活站在用户看得见的接口上，所以它的三态与调用次数都要钉住。
# ---------------------------------------------------------------------------


def _probe(post, *, ak: str | None = "probe-ak") -> bool | None:
    """换掉 AK 与 ``requests.post``，跑一次 ``probe_credentials``。"""
    ali_client._probe_cache.clear()
    with patch.object(ali_client, "raw_ak", lambda: ak), \
         patch.object(ali_client, "build_auth_headers", lambda *a, **k: {"Content-Type": "application/json"}), \
         patch.object(ali_client.time, "sleep", lambda *_: None), \
         patch.object(ali_client.requests, "post", post):
        return ali_client.probe_credentials()


def test_probe_is_true_when_the_gateway_answers() -> None:
    """网关答了话就是凭据过关 —— 哪怕它嫌这次请求参数不对。

    ``ParamMissing`` 恰恰是「收下了、只是不满意请求」：凭据好得很。把这种也算成失效，
    用户会被推去白扫一次码。
    """
    out = _probe(_returns(_Resp(400, {"code": "ParamMissing", "message": "缺少参数"})))

    assert out is True


def test_probe_is_false_when_the_gateway_rejects_the_credential() -> None:
    """【回归】AK 过期 → False。这条就是这次要修的洞：本地文件还在，但网关不认了。"""
    out = _probe(_returns(_Resp(400, _AK_EXPIRED)))

    assert out is False


def test_probe_is_false_on_signature_failure() -> None:
    """签名校验失败也指向凭据本身（secret 不对），不是「没问到」。"""
    out = _probe(_returns(_Resp(200, {"success": False, "code": "SignatureInvalid"})))

    assert out is False


def test_probe_is_none_when_the_gateway_cannot_be_reached() -> None:
    """网络不通 → None，**不是** False。

    缩成 bool 的话这里必须是 False，而前端拿到 False 会弹「登录已过期，请重新扫码」：
    一次网络抖动换用户白扫一次码，比多显示一会儿「已登录」更糟。
    """
    def boom(*args: Any, **kwargs: Any):
        raise ali_client.requests.exceptions.ConnectionError("conn refused")

    assert _probe(boom) is None


def test_probe_is_none_on_gateway_5xx() -> None:
    """网关自己 5xx → None：不知道是谁的问题，就别动用户的登录状态。"""
    assert _probe(_returns(_Resp(500, None, is_json=False))) is None


def test_probe_without_ak_is_false_and_touches_no_network() -> None:
    """本地根本没配 AK → False，且不发请求。"""
    def boom(*args: Any, **kwargs: Any):
        raise AssertionError("不该发请求")

    assert _probe(boom, ak=None) is False


def test_probe_tries_the_gateway_only_once() -> None:
    """探活只打一次 —— 它站在账号列表的调用路径上，不该蹲三轮退避。

    拿 5xx 触发：``_with_retry`` 在普通调用里对它要重试 ``MAX_RETRIES`` 次，
    所以次数是 1 就证明 ``_retries=1`` 真传下去了。
    """
    calls: list[int] = []

    def counting(*args: Any, **kwargs: Any) -> _Resp:
        calls.append(1)
        return _Resp(500, None, is_json=False)

    _probe(counting)

    assert len(calls) == 1


def test_probe_caches_a_definite_verdict() -> None:
    """确定的结论按 AK 缓存：前端账号页每 30s 拉一次列表，不缓存就是拿找货接口当心跳打。"""
    calls: list[int] = []

    def counting(*args: Any, **kwargs: Any) -> _Resp:
        calls.append(1)
        return _Resp(400, _AK_EXPIRED)

    ali_client._probe_cache.clear()
    with patch.object(ali_client, "raw_ak", lambda: "probe-ak"), \
         patch.object(ali_client, "build_auth_headers", lambda *a, **k: {"Content-Type": "application/json"}), \
         patch.object(ali_client.time, "sleep", lambda *_: None), \
         patch.object(ali_client.requests, "post", counting):
        first = ali_client.probe_credentials()
        second = ali_client.probe_credentials()

    assert (first, second) == (False, False)
    assert len(calls) == 1


def test_probe_does_not_cache_an_unknown() -> None:
    """「没问到」不缓存 —— 网络一恢复下次就要能问到，别被一次抖动锁 5 分钟。"""
    calls: list[int] = []

    def flaky(*args: Any, **kwargs: Any) -> _Resp:
        calls.append(1)
        if len(calls) == 1:
            raise ali_client.requests.exceptions.ConnectionError("conn refused")
        return _Resp(200, {"code": "Success", "model": {"data": []}})

    ali_client._probe_cache.clear()
    with patch.object(ali_client, "raw_ak", lambda: "probe-ak"), \
         patch.object(ali_client, "build_auth_headers", lambda *a, **k: {"Content-Type": "application/json"}), \
         patch.object(ali_client.time, "sleep", lambda *_: None), \
         patch.object(ali_client.requests, "post", flaky):
        first = ali_client.probe_credentials()
        second = ali_client.probe_credentials()

    assert (first, second) == (None, True)
    assert len(calls) == 2


def test_probe_cache_is_keyed_by_the_ak() -> None:
    """换了 AK 就是换了凭据，旧结论不许粘在新的上面。"""
    ak = "old-ak"

    def post(*args: Any, **kwargs: Any) -> _Resp:
        # 老 AK 被拒、新 AK 被认 —— 缓存要是没按 AK 分桶，第二次会读到第一次的 False
        return _Resp(400, _AK_EXPIRED) if ak == "old-ak" else _Resp(200, {"code": "Success", "model": {"data": []}})

    ali_client._probe_cache.clear()
    with patch.object(ali_client, "raw_ak", lambda: ak), \
         patch.object(ali_client, "build_auth_headers", lambda *a, **k: {"Content-Type": "application/json"}), \
         patch.object(ali_client.time, "sleep", lambda *_: None), \
         patch.object(ali_client.requests, "post", post):
        stale = ali_client.probe_credentials()
        ak = "new-ak"
        fresh = ali_client.probe_credentials()

    assert (stale, fresh) == (False, True)
