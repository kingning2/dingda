"""系统 Chrome 启动（扫码风控恢复用）。"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("dingda.channel.chrome")

SYSTEM_CHANNELS = ("chrome", "msedge")
LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-popup-blocking",
]


def clear_profile_locks(user_data_dir: Path) -> None:
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        lock = user_data_dir / name
        with contextlib.suppress(OSError):
            if lock.exists():
                lock.unlink()


def to_serializable_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", ""),
            "expires": c.get("expires"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": c.get("sameSite") or "Lax",
        }
        for c in cookies
        if c.get("name") and c.get("value")
    ]


async def launch_chrome_context(
    playwright: Any,
    user_data_dir: Path,
    *,
    headless: bool,
) -> Any:
    clear_profile_locks(user_data_dir)
    user_data_dir.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "headless": headless,
        "args": list(LAUNCH_ARGS),
        "ignore_default_args": ["--enable-automation"],
        "viewport": {"width": 1280, "height": 800},
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }
    last_error: str | None = None
    for channel in SYSTEM_CHANNELS + (None,):
        opts = dict(kwargs)
        if channel:
            opts["channel"] = channel
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(user_data_dir),
                **opts,
            )
            logger.info("Chrome 已启动 channel=%s headless=%s", channel or "bundled", headless)
            return context
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Chrome 启动失败 channel=%s: %s", channel, str(exc)[:120])
    raise RuntimeError(f"启动 Chrome 失败: {last_error}")
