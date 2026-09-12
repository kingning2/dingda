"""爬虫 / 预览用账号 Cookie 与会话解析。

职责：
    请求未显式传 cookie 时，从账号库取该平台「已连接且登录有效」的 cookie。
    商品预览另取 localStorage，并按平台映射成可注入 WebView 的 Cookie 列表。
    供 crawler HTTP / Tool / 桌面预览窗使用，不碰 Playwright。

设计说明：
    - 「已连接」是产品开关；扫码存的 cookie 才是登录态
    - 未连接或无 cookie 时返回 None，由平台页自己报登录/风控
    - 域名映射留在 channels/<platform>/cookies，本模块只编排

使用示例：
    cookie = resolve_crawl_cookie("xianyu", body.cookie)
    session = resolve_browser_session("xianyu")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from contracts.browser_port import Cookie
from channels.cookie_header import parse_cookie_header
from infrastructure.db import accounts as account_repo

logger = logging.getLogger("dingda.crawler.account_cookie")


@dataclass(frozen=True, slots=True)
class BrowserSession:
    """可注入浏览器的平台登录会话。"""

    platform: str
    account_id: str
    cookie: str
    cookies: tuple[Cookie, ...]
    local_storage: dict[str, str]


def resolve_crawl_cookie(platform: str, cookie: str | None = None) -> str | None:
    """优先用入参 cookie；否则取平台已连接账号，再退到仅登录有效的账号。"""
    explicit = (cookie or "").strip()
    if explicit:
        return explicit

    session = resolve_browser_session(platform)
    return session.cookie if session else None


def resolve_browser_session(platform: str) -> BrowserSession | None:
    """取平台可用账号的 cookie + localStorage + 域名 Cookie 列表。"""
    plat = platform.strip().lower()
    if not plat or plat == "ali1688":
        # 1688 走 AK，不靠浏览器 cookie
        return None

    row = _pick_account_row(plat)
    if row is None:
        logger.info("browser session missing platform=%s (no usable account)", plat)
        return None

    cookie = (row.cookie or "").strip()
    if not cookie:
        logger.info("browser session missing cookie platform=%s account=%s", plat, row.account_id)
        return None

    cookies = _cookies_for_platform(plat, cookie)
    local_storage = _parse_local_storage(row.local_storage)
    logger.info(
        "browser session ready platform=%s account=%s cookies=%s local_storage=%s",
        plat,
        row.account_id,
        len(cookies),
        len(local_storage),
    )
    return BrowserSession(
        platform=plat,
        account_id=row.account_id,
        cookie=cookie,
        cookies=tuple(cookies),
        local_storage=local_storage,
    )


def _pick_account_row(platform: str):
    """优先已连接且登录有效，再退到仅登录有效。"""
    rows = account_repo.list_accounts(platform=platform)
    for row in rows:
        if not row.connected or not row.auth_valid:
            continue
        if (row.cookie or "").strip():
            logger.info(
                "crawl cookie from connected account platform=%s account=%s",
                platform,
                row.account_id,
            )
            return row

    for row in rows:
        if not row.auth_valid:
            continue
        if (row.cookie or "").strip():
            logger.info(
                "crawl cookie from auth_valid account platform=%s account=%s connected=%s",
                platform,
                row.account_id,
                row.connected,
            )
            return row
    return None


def _cookies_for_platform(platform: str, cookie_header: str) -> list[Cookie]:
    """按平台把 cookie 头收成 Browser Cookie（含域名）。"""
    parsed = parse_cookie_header(cookie_header)
    if not parsed:
        return []
    if platform == "xiaohongshu":
        from channels.xiaohongshu.cookies import to_browser_cookies

        return to_browser_cookies(parsed)
    if platform == "xianyu":
        from channels.xianyu.cookies import to_browser_cookies

        return to_browser_cookies(parsed)
    return []


def _parse_local_storage(raw: str | None) -> dict[str, str]:
    """账号库 local_storage JSON → dict。"""
    text = (raw or "").strip() or "{}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("local_storage JSON 无效，忽略")
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        name = str(key or "").strip()
        if not name:
            continue
        out[name] = "" if value is None else str(value)
    return out
