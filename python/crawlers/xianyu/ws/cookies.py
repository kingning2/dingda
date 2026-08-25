"""Cookie 解析 — 对齐 Rust `shared::cookies` 子集。"""

from __future__ import annotations

import hashlib
import time
from typing import Any


def now_ms() -> int:
    return int(time.time() * 1000)


def parse_cookies(raw: str | list[dict[str, Any]]) -> dict[str, str]:
    if isinstance(raw, list):
        out: dict[str, str] = {}
        for item in raw:
            name = str(item.get("name") or "").strip()
            if name:
                out[name] = str(item.get("value") or "")
        return out
    result: dict[str, str] = {}
    for part in str(raw).split(";"):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        name, value = piece.split("=", 1)
        result[name.strip()] = value.strip()
    return result


def cookies_to_header(cookies: str | list[dict[str, Any]]) -> str:
    if isinstance(cookies, list):
        return "; ".join(f"{name}={value}" for name, value in parse_cookies(cookies).items())
    return str(cookies).strip()


def credential_to_cookie_header(credential: str | list[dict[str, Any]]) -> str:
    """续期 JSON 数组或 Cookie 串 → Cookie Header。"""
    if isinstance(credential, list):
        return cookies_to_header(credential)
    raw = str(credential).strip()
    if not raw:
        return ""
    if raw.startswith("["):
        try:
            import json

            parsed = json.loads(raw)
            if isinstance(parsed, list):
                header = cookies_to_header(parsed)
                if header:
                    return header
        except Exception:  # noqa: BLE001
            pass
    return cookies_to_header(raw)


def my_id(cookies: dict[str, str]) -> str | None:
    unb = cookies.get("unb", "").strip()
    return unb or None


def sign_token(cookies: dict[str, str]) -> str | None:
    raw = cookies.get("_m_h5_tk", "").strip()
    if not raw:
        return None
    return raw.split("_", 1)[0] or None


def device_id_from_cookie(cookie_header: str) -> str | None:
    cookies = parse_cookies(cookie_header)
    unb = my_id(cookies)
    if not unb:
        return None
    digest = hashlib.md5(unb.encode("utf-8")).hexdigest()  # noqa: S324
    return digest


def clean_cookie_header(value: str) -> str:
    return "".join(ch for ch in value if ch == "\t" or (" " <= ch <= "~"))
