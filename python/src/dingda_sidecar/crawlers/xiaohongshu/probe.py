"""小红书登录态探针 — 带签名的 ``GET /api/sns/web/v2/user/me``。

以 ``data.guest === false`` 判定已登录；``web_session`` 单独存在不代表登录态有效。
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from dingda_sidecar.crawlers.goofish.ws.cookies import cookies_to_header, parse_cookies

logger = logging.getLogger("dingda.sidecar.xiaohongshu.probe")

_USER_ME_URL = "https://edith.xiaohongshu.com/api/sns/web/v2/user/me"
_USER_ME_URI = "/api/sns/web/v2/user/me"
_XHS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
_SIGN_COOKIE_KEYS = ("a1", "web_session", "webId", "websectiga", "sec_po", "gid")


def _offline(
    *,
    detail: str,
    status: str = "offline",
    ok: bool = True,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "online": False,
        "status": status,
        "detail": detail,
        "cookies": None,
    }


def _online(*, detail: str, cookies: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ok": True,
        "online": True,
        "status": "online",
        "detail": detail,
        "cookies": cookies,
    }


def _cookies_to_request_map(cookies: list[dict[str, Any]]) -> dict[str, str]:
    parsed = parse_cookies(cookies)
    return {key: parsed[key] for key in _SIGN_COOKIE_KEYS if parsed.get(key)}


def _unwrap_user_me_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


def _is_logged_in(payload: dict[str, Any]) -> bool:
    inner = _unwrap_user_me_payload(payload)
    return inner.get("guest") is False


def _merge_response_cookies(
    session: requests.Session,
    base_cookies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in base_cookies:
        name = str(item.get("name") or "").strip()
        if name:
            merged[name] = dict(item)
    for cookie in session.cookies:
        domain = str(cookie.domain or "")
        if "xiaohongshu.com" not in domain.lower():
            continue
        merged[str(cookie.name)] = {
            "name": str(cookie.name),
            "value": str(cookie.value),
            "domain": domain or ".xiaohongshu.com",
            "path": str(cookie.path or "/"),
        }
    return list(merged.values())


def probe_xiaohongshu_session(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    """签名请求 ``/user/me`` 探活；成功时回传（可能合并 Set-Cookie 后的）Cookie。"""
    header = cookies_to_header(cookies)
    if not header:
        return _offline(detail="无有效 Cookie", status="error", ok=False)

    request_cookies = _cookies_to_request_map(cookies)
    a1 = request_cookies.get("a1")
    if not a1:
        return _offline(detail="缺少 a1 Cookie，无法签名探活")

    try:
        from xhshow import Xhshow
    except ImportError as error:
        logger.exception("xhshow 未安装，无法签名探活")
        return _offline(detail=f"签名依赖缺失: {error}", status="error", ok=False)

    client = Xhshow()
    try:
        sign_headers = client.sign_headers_get(uri=_USER_ME_URI, cookies=request_cookies)
    except Exception as error:  # noqa: BLE001
        logger.exception("小红书 user/me 签名失败")
        return _offline(detail=f"签名失败: {error}", status="error", ok=False)

    session = requests.Session()
    headers = {
        "User-Agent": _XHS_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": "https://www.xiaohongshu.com",
        "Referer": "https://www.xiaohongshu.com/",
        **sign_headers,
    }

    try:
        response = session.get(
            _USER_ME_URL,
            headers=headers,
            cookies=request_cookies,
            timeout=20,
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("小红书 user/me 请求异常")
        return _offline(detail=str(error), status="error", ok=False)

    if response.status_code >= 400:
        body = response.text[:200]
        logger.info(
            "小红书 user/me HTTP 失败 status=%s body=%s",
            response.status_code,
            body,
        )
        return _offline(
            detail=f"HTTP {response.status_code}: {body}",
            status="offline" if response.status_code in {401, 403} else "error",
            ok=response.status_code in {401, 403},
        )

    try:
        payload = response.json()
    except ValueError as error:
        return _offline(detail=f"响应非 JSON: {error}", status="error", ok=False)

    if not isinstance(payload, dict):
        return _offline(detail="响应格式异常", status="error", ok=False)

    success = payload.get("success")
    code = payload.get("code")
    if success is False or (isinstance(code, int) and code not in {0, 200}):
        message = str(payload.get("msg") or payload.get("message") or code or "unknown")
        logger.info("小红书 user/me 业务失败 code=%s msg=%s", code, message[:120])
        return _offline(detail=f"code={code} {message}")

    online = _is_logged_in(payload)
    inner = _unwrap_user_me_payload(payload)
    guest = inner.get("guest")
    user_id = inner.get("user_id") or inner.get("userId")
    exported = _merge_response_cookies(session, cookies)

    logger.info(
        "小红书 user/me 探活完成 online=%s guest=%s user_id=%s",
        online,
        guest,
        user_id,
    )
    if not online:
        return _offline(detail=f"guest={guest} user_id={user_id or '-'}")

    return _online(
        detail=f"guest=false user_id={user_id or '-'}",
        cookies=exported,
    )
