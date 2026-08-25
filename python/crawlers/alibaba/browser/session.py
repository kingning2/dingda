"""1688 Camoufox 会话辅助 — Cookie 注入、profile 目录、风控 URL 判定。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

LOGIN_REDIRECT_MARKERS = (
    "/punish",
    "x5secdata=",
    "login.taobao.com",
    "login.1688.com",
)


def safe_account_dir(account_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", account_id.strip()) or "unknown"
    return cleaned[:80]


def profile_dir(account_id: str) -> Path:
    configured = os.getenv("DINGDA_1688_BROWSER_PROFILE", "").strip()
    if not configured:
        configured = os.getenv("DINGDA_1688_SEARCH_PROFILE", "").strip()
    if configured:
        return Path(configured)
    return Path.cwd() / "browser_data" / f"user_{safe_account_dir(account_id)}"


def resolve_headless(*, headed: bool | None, env_key: str, default_headless: bool) -> bool:
    if headed is not None:
        return not headed
    value = os.getenv(env_key, "1" if default_headless else "0").strip().lower()
    if default_headless:
        return value not in {"0", "false", "no", "off"}
    return value in {"1", "true", "yes", "on"}


def playwright_cookie(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = str(raw.get("name") or "").strip()
    value = str(raw.get("value") or "").strip()
    if not name or not value:
        return None
    domain = str(raw.get("domain") or "").strip() or ".1688.com"
    if domain.startswith("http"):
        domain = ".1688.com"
    path = str(raw.get("path") or "").strip() or "/"
    cookie: dict[str, Any] = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
    }
    http_only = raw.get("httpOnly")
    if http_only is None:
        http_only = raw.get("http_only")
    if isinstance(http_only, bool):
        cookie["httpOnly"] = http_only
    if isinstance(raw.get("secure"), bool):
        cookie["secure"] = raw["secure"]
    same_site = raw.get("sameSite") or raw.get("same_site")
    if isinstance(same_site, str) and same_site:
        cookie["sameSite"] = same_site
    return cookie


def prepare_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for raw in cookies:
        if not isinstance(raw, dict):
            continue
        cookie = playwright_cookie(raw)
        if cookie:
            prepared.append(cookie)
    return prepared


def looks_blocked(url: str) -> bool:
    lowered = (url or "").lower()
    return any(marker in lowered for marker in LOGIN_REDIRECT_MARKERS)
