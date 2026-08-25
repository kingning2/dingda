"""mtop login token — WebSocket ``/reg`` 前置。

用 Cookie 拉取登录 token，必要时探测/合并 Set-Cookie，失败时抛出 TokenError。"""

from __future__ import annotations

import contextlib
import json
import logging
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

from crawlers.xianyu.risk import RiskControlError, extract_punish_url, is_risk_control_text
from crawlers.xianyu.ws.constants import APP_KEY, LOGIN_TOKEN_URL, REG_APP_KEY, TOKEN_CACHE_TTL_SEC
from crawlers.xianyu.ws.cookies import (
    cookies_to_header,
    device_id_from_cookie,
    merge_cookie_header,
    my_id,
    parse_cookies,
    sign_token,
)
from crawlers.xianyu.ws.sign import generate_sign

logger = logging.getLogger("dingda.crawlers.xianyu.ws.token")

_token_cache: dict[str, tuple[str, float]] = {}


class TokenError(Exception):
    pass


def fetch_ws_token(cookies: str | list[dict[str, Any]], *, force_refresh: bool = False) -> str:
    """获取 WebSocket 注册 token（带 unb 级内存缓存，默认 TTL 30 分钟）。"""
    header = cookies_to_header(cookies)
    parsed = parse_cookies(cookies)
    unb = my_id(parsed)
    if not unb:
        raise TokenError("cookie 缺少 unb")

    if not force_refresh:
        cached = _token_cache.get(unb)
        if cached is not None:
            token, saved_at = cached
            if time.time() - saved_at < TOKEN_CACHE_TTL_SEC:
                return token

    token = _fetch_ws_token_uncached(header)
    _token_cache[unb] = (token, time.time())
    return token


def refresh_login(
    cookies: str | list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """长连保活：调用 ``mtop.taobao.idlemessage.pc.loginuser.get``。"""
    from crawlers.xianyu.mtop import MtopClient, MtopRequest

    header = cookies_to_header(cookies)
    client = MtopClient(header)
    response = client.call(
        MtopRequest(
            api="mtop.taobao.idlemessage.pc.loginuser.get",
            version="1.0",
            data={},
            extra_params={"spm_cnt": "a21ybx.im.0.0"},
        ),
    )
    base = (
        cookies
        if isinstance(cookies, list)
        else [{"name": name, "value": value} for name, value in parse_cookies(cookies).items()]
    )
    updated = merge_cookie_header(client.cookie, base)
    return response.json, updated


def _fetch_ws_token_uncached(header: str) -> str:
    """获取 WebSocket 注册 token（无缓存）。"""
    jar = CookieJar()
    parsed = parse_cookies(header)

    if not my_id(parsed):
        raise TokenError("cookie 缺少 unb")

    current = sign_token(parsed) or ""
    if not current:
        header = _probe_for_h5_tk(header, jar)

    last_error = "token 获取失败"
    for attempt in range(3):
        parsed = parse_cookies(header)
        token_part = sign_token(parsed) or ""
        if not token_part:
            raise TokenError("cookie 缺少 _m_h5_tk，请重新登录")
        try:
            return _fetch_once(header, token_part, jar)
        except TokenError as error:
            last_error = str(error)
            refreshed = _merge_set_cookie(header, jar)
            if refreshed == header:
                break
            header = refreshed
            logger.info("mtop token 刷新重试 attempt=%s", attempt + 1)
    raise TokenError(last_error)


def _probe_for_h5_tk(header: str, jar: CookieJar) -> str:
    with contextlib.suppress(TokenError):
        _fetch_once(header, "", jar)
    return _merge_set_cookie(header, jar)


def _fetch_once(header: str, token_part: str, jar: CookieJar) -> str:
    device_id = device_id_from_cookie(header)
    if not device_id:
        raise TokenError("无法解析 deviceId")

    from crawlers.xianyu.ws.cookies import now_ms

    data_val = json.dumps({"appKey": REG_APP_KEY, "deviceId": device_id}, separators=(",", ":"))
    timestamp = str(now_ms())
    sign = generate_sign(token_part, timestamp, data_val)

    query = urllib.parse.urlencode(
        {
            "jsv": "2.7.2",
            "appKey": APP_KEY,
            "t": timestamp,
            "sign": sign,
            "v": "1.0",
            "type": "originaljson",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": "mtop.taobao.idlemessage.pc.login.token",
            "sessionOption": "AutoLoginOnly",
            "data": data_val,
        },
    )
    url = f"{LOGIN_TOKEN_URL}?{query}"
    req = urllib.request.Request(  # noqa: S310
        url,
        data=data_val.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": header,
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:  # noqa: S310
        body = response.read().decode("utf-8", errors="replace")
        set_cookie = response.headers.get("Set-Cookie")
        if set_cookie:
            _apply_set_cookie(jar, set_cookie)

    payload = json.loads(body)
    token = (payload.get("data") or {}).get("accessToken") or (payload.get("data") or {}).get(
        "token"
    )
    if isinstance(token, str) and token.strip():
        return token.strip()

    ret = str(payload.get("ret") or payload.get("message") or body)
    if "SESSION_EXPIRED" in ret or "FAIL_SYS_SESSION_EXPIRED" in ret:
        raise TokenError("登录态已过期，请重新扫码登录")
    if is_risk_control_text(ret) or is_risk_control_text(body):
        raise RiskControlError(
            f"token 接口未成功: {ret[:400]}",
            punish_url=extract_punish_url(body) or extract_punish_url(ret),
        )
    raise TokenError(f"token 接口失败: {ret[:200]}")


def _merge_set_cookie(header: str, jar: CookieJar) -> str:
    cookies = parse_cookies(header)
    for cookie in jar:
        cookies[cookie.name] = cookie.value
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _apply_set_cookie(jar: CookieJar, header: str) -> None:
    for part in header.split(","):
        piece = part.strip().split(";", 1)[0]
        if "=" not in piece:
            continue
        name, value = piece.split("=", 1)
        jar.set_cookie(
            urllib.request.cookiejar.Cookie(
                version=0,
                name=name.strip(),
                value=value.strip(),
                port=None,
                port_specified=False,
                domain=".goofish.com",
                domain_specified=True,
                domain_initial_dot=True,
                path="/",
                path_specified=True,
                secure=False,
                expires=None,
                discard=True,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            ),
        )
