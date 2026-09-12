"""闲鱼 Cookie 域名映射与 Browser 注入转换。

职责：
    按 cookie 名选择 .taobao.com / .goofish.com 注入域名；
    关键 cookie 同时写两边，避免 passport 弹登录框。
    在 dict 与 BrowserPort Cookie 间转换。

设计说明：
    - 平台特例留在 Channel，不进 browser/adapters
    - 调用方：session、mtop 续期、renew、tools/search|product 的 cookie 注入

使用示例：
    cookies = to_browser_cookies(parse_cookie_header(header))
"""

from __future__ import annotations

import time
from typing import Any

from contracts.browser_port import Cookie

# 淘系签名 cookie 主域 .taobao.com
_TAOBAO_COOKIE_NAMES = {
    "_m_h5_tk",
    "_m_h5_tk_enc",
    "x5sec",
    "sgcookie",
    "cookie2",
    "_tb_token_",
}

# 登录态关键字段：两边都写，passport / goofish 都能认
_DUAL_DOMAIN_NAMES = {
    "unb",
    "cookie2",
    "_tb_token_",
    "sgcookie",
    "_m_h5_tk",
    "_m_h5_tk_enc",
    "tracknick",
    "cna",
    "t",
    "havana_lgc2_0",
    "havana_lgc_exp",
    "lgc",
    "sn",
}


def cookie_domain(name: str) -> str:
    """按 cookie 名选择闲鱼主注入域名。"""
    return ".taobao.com" if name in _TAOBAO_COOKIE_NAMES else ".goofish.com"


def to_browser_cookies(cookies: dict[str, str]) -> list[Cookie]:
    """`{name: value}` → Browser Cookie 列表（登录关键字段双域写入）。"""
    expires = int(time.time()) + 7 * 24 * 3600
    out: list[Cookie] = []
    seen: set[tuple[str, str]] = set()

    def _add(name: str, value: str, domain: str) -> None:
        key = (name, domain)
        if key in seen:
            return
        seen.add(key)
        out.append(
            Cookie(
                name=name,
                value=value,
                domain=domain,
                path="/",
                expires=expires,
                http_only=False,
                secure=True,
                same_site="None",
            )
        )

    for name, value in cookies.items():
        if not value:
            continue
        primary = cookie_domain(name)
        _add(name, value, primary)
        if name in _DUAL_DOMAIN_NAMES:
            other = ".goofish.com" if primary == ".taobao.com" else ".taobao.com"
            _add(name, value, other)
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
