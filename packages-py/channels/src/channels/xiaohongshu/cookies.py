"""小红书 Cookie 与 Browser 注入转换。

职责：
    把账号 cookie dict 收成 BrowserPort Cookie，域名统一 ``.xiaohongshu.com``。

设计说明：
    - 平台特例留在 Channel，不进 browser/adapters
    - 调用方：tools/search、product 注入会话

使用示例：
    cookies = to_browser_cookies(parse_cookie_header(header))
"""

from __future__ import annotations

import time
from typing import Any

from contracts.browser_port import Cookie

COOKIE_DOMAIN = ".xiaohongshu.com"


def to_browser_cookies(cookies: dict[str, str]) -> list[Cookie]:
    """`{name: value}` → Browser Cookie 列表（小红书域名）。"""
    expires = int(time.time()) + 7 * 24 * 3600
    out: list[Cookie] = []
    for name, value in cookies.items():
        if not value:
            continue
        out.append(
            Cookie(
                name=name,
                value=value,
                domain=COOKIE_DOMAIN,
                path="/",
                expires=expires,
                http_only=False,
                secure=True,
                same_site="Lax",
            )
        )
    return out


def cookie_map(raw_cookies: list[dict[str, Any]] | list[Cookie]) -> dict[str, str]:
    """Cookie 列表 → `{name: value}`。"""
    out: dict[str, str] = {}
    for entry in raw_cookies:
        if isinstance(entry, Cookie):
            if entry.name and entry.value:
                out[entry.name] = entry.value
            continue
        name = entry.get("name")
        value = entry.get("value")
        if name and value:
            out[str(name)] = str(value)
    return out
