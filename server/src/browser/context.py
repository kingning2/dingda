"""浏览器 Context 选项：把代理 / 指纹 / Cookie 收成一次 open 的入参。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.browser.port import Cookie


@dataclass(frozen=True)
class ContextOptions:
    """一次开页的策略（由 BrowserCrawler / Session 传入，Adapter 执行）。"""

    proxy_url: str | None = None
    fingerprint_profile: str | None = None
    cookies: Sequence[Cookie] | Mapping[str, str] | None = None
    default_cookie_domain: str = ""
    locale: str = "zh-CN"
    viewport_width: int = 1280
    viewport_height: int = 800


def normalize_cookies(
    cookies: Sequence[Cookie] | Mapping[str, str] | None,
    *,
    default_domain: str = "",
) -> list[Cookie]:
    """把 dict 或 Cookie 列表收成统一 Cookie 列表；dict 需要 default_domain。"""
    if not cookies:
        return []
    if isinstance(cookies, Mapping):
        if not default_domain:
            raise ValueError("dict cookies 需要 default_domain")
        return [
            Cookie(name=str(name), value=str(value), domain=default_domain)
            for name, value in cookies.items()
            if value
        ]
    return list(cookies)


def cookies_to_playwright(cookies: Sequence[Cookie]) -> list[dict[str, object]]:
    """Cookie → Playwright add_cookies 字典（无平台域名映射）。"""
    out: list[dict[str, object]] = []
    for cookie in cookies:
        if not cookie.name or not cookie.value:
            continue
        entry: dict[str, object] = {
            "name": cookie.name,
            "value": cookie.value,
            "path": cookie.path or "/",
            "httpOnly": cookie.http_only,
            "secure": cookie.secure,
            "sameSite": cookie.same_site or "Lax",
        }
        if cookie.domain:
            entry["domain"] = cookie.domain
        if cookie.expires is not None:
            entry["expires"] = cookie.expires
        out.append(entry)
    return out


def proxy_server(proxy_url: str | None) -> dict[str, str] | None:
    """代理 URL → Playwright proxy 参数。"""
    if not proxy_url:
        return None
    return {"server": proxy_url}


def serialize_cookies(cookies: list[dict[str, object]]) -> list[dict[str, object]]:
    """把 Playwright Cookie 字典收成可序列化导出结构。"""
    out: list[dict[str, object]] = []
    for cookie in cookies:
        name = cookie.get("name", "")
        value = cookie.get("value", "")
        if not name or not value:
            continue
        out.append(
            {
                "name": name,
                "value": value,
                "domain": cookie.get("domain", ""),
                "path": cookie.get("path", ""),
                "expires": cookie.get("expires"),
                "httpOnly": cookie.get("httpOnly", False),
                "secure": cookie.get("secure", False),
                "sameSite": cookie.get("sameSite") or "Lax",
            }
        )
    return out
