"""闲鱼 Cookie 域名映射与 Browser 注入转换。

职责：
    按 cookie 名选择 .taobao.com / .goofish.com 注入域名；
    在 dict 与 BrowserPort Cookie 间转换。

设计说明：
    - 平台特例留在 Channel，不进 browser/adapters
    - 调用方：session、mtop 续期、renew、tools/search|product 的 cookie 注入
"""

from __future__ import annotations

import time
from typing import Any

from src.browser.port import Cookie

# 淘系签名 cookie 走 .taobao.com，其余走 .goofish.com（对齐 goofish_cli）
_TAOBAO_COOKIE_NAMES = {
    "_m_h5_tk",
    "_m_h5_tk_enc",
    "x5sec",
    "sgcookie",
    "cookie2",
    "_tb_token_",
}


def cookie_domain(name: str) -> str:
    """按 cookie 名选择闲鱼注入域名。"""
    return ".taobao.com" if name in _TAOBAO_COOKIE_NAMES else ".goofish.com"


def to_browser_cookies(cookies: dict[str, str]) -> list[Cookie]:
    """`{name: value}` → Browser Cookie 列表（带闲鱼域名）。"""
    expires = int(time.time()) + 7 * 24 * 3600
    out: list[Cookie] = []
    for name, value in cookies.items():
        if not value:
            continue
        out.append(
            Cookie(
                name=name,
                value=value,
                domain=cookie_domain(name),
                path="/",
                expires=expires,
                http_only=False,
                secure=True,
                same_site="None",
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
