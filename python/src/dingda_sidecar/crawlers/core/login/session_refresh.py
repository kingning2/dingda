"""闲鱼 HTTP 会话刷新 / 小红书签名探活（非浏览器）。

- 闲鱼：HTTP 刷新 token，成功则返回更新后的 Cookie
- 小红书：签名 ``/user/me`` 探活，``guest=false`` 视为在线
"""

from __future__ import annotations

import logging
from typing import Any

from dingda_sidecar.crawlers.core.platform_config import normalize_platform
from dingda_sidecar.crawlers.goofish.ws.cookies import (
    cookies_to_header,
    merge_cookie_header,
    parse_cookies,
)
from dingda_sidecar.crawlers.goofish.ws.token import TokenError, fetch_ws_token, refresh_login

logger = logging.getLogger("dingda.sidecar.session-refresh")


def _session_expired_text(text: str) -> bool:
    upper = text.upper()
    return (
        "SESSION_EXPIRED" in upper
        or "FAIL_SYS_SESSION_EXPIRED" in upper
        or "登录态已过期" in text
        or "请重新扫码" in text
    )


def refresh_xianyu_session(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    """HTTP 刷新闲鱼 token（mtop loginuser + WS token 校验）。"""
    if not cookies:
        return {
            "ok": False,
            "online": False,
            "status": "error",
            "detail": "无有效 Cookie",
            "cookies": None,
        }
    try:
        _, updated = refresh_login(cookies)
        fetch_ws_token(updated, force_refresh=True)
        exported = merge_cookie_header(cookies_to_header(updated), cookies)
        parsed = parse_cookies(updated)
        if not parsed.get("unb") or not parsed.get("_m_h5_tk"):
            return {
                "ok": True,
                "online": False,
                "status": "offline",
                "detail": "刷新后缺少 unb / _m_h5_tk",
                "cookies": None,
            }
        logger.info("闲鱼 HTTP token 刷新成功 cookies=%s", len(exported))
        return {
            "ok": True,
            "online": True,
            "status": "online",
            "detail": "HTTP token 刷新成功",
            "cookies": exported,
        }
    except TokenError as error:
        detail = str(error)
        expired = _session_expired_text(detail)
        logger.info("闲鱼 HTTP token 刷新失败 expired=%s detail=%s", expired, detail[:120])
        return {
            "ok": True,
            "online": False,
            "status": "offline" if expired else "error",
            "detail": detail,
            "cookies": None,
        }
    except Exception as error:  # noqa: BLE001
        logger.exception("闲鱼 HTTP token 刷新异常")
        return {
            "ok": False,
            "online": False,
            "status": "error",
            "detail": str(error),
            "cookies": None,
        }


def refresh_xiaohongshu_session(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    """签名 ``/user/me`` 探活（无独立 refresh_token，不刷新 Cookie）。"""
    from dingda_sidecar.crawlers.xiaohongshu.probe import probe_xiaohongshu_session

    return probe_xiaohongshu_session(cookies)


def refresh_session_http(
    platform: str,
    cookies: list[dict[str, Any]],
    *,
    account_id: str,
) -> dict[str, Any]:
    """按平台分发：闲鱼 HTTP 刷新 / 小红书签名探活。"""
    del account_id
    name = normalize_platform(platform)
    if name == "xianyu":
        return refresh_xianyu_session(cookies)
    if name == "xiaohongshu":
        return refresh_xiaohongshu_session(cookies)
    return {
        "ok": False,
        "online": False,
        "status": "unsupported_platform",
        "detail": f"HTTP 会话刷新不支持平台: {name}",
        "cookies": None,
    }
