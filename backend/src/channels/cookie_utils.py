"""Cookie 字符串解析。"""

from __future__ import annotations


def parse_cookie_header(cookie: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in cookie.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


def cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())
