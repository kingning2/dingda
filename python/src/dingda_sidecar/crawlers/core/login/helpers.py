"""扫码登录公用 helper（页面文本、截图、Cookie 判定等）。

把二维码截图转 data URL、从页面文案推断进度，并按平台 Cookie 域判断是否已登录。"""

from __future__ import annotations

import base64
import contextlib
import os
from typing import Any

from dingda_sidecar.crawlers.core.platform_config import get_platform_config

_SCANNED_MARKERS = ("已扫码", "扫码成功", "扫描成功", "扫码完成")
_CONFIRMED_MARKERS = (
    "确认登录",
    "请在手机上确认",
    "请在手机确认",
    "请在手机",
)
_SUCCESS_TEXT_MARKERS = ("登录成功",)


def to_qr_data_url(screenshot: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(screenshot).decode("ascii")


def login_progress_from_text(page_text: str) -> str | None:
    text = (page_text or "").strip()
    if not text:
        return None
    if any(marker in text for marker in _SUCCESS_TEXT_MARKERS) and "欢迎" in text:
        return "success_text"
    if "登录成功" in text:
        return "success_text"
    scanned = any(marker in text for marker in _SCANNED_MARKERS)
    if scanned and "确认" in text:
        return "scanned"
    if any(marker in text for marker in _CONFIRMED_MARKERS):
        return "confirmed"
    if scanned:
        return "scanned"
    if "确认" in text and "二维码" in text:
        return "confirmed"
    return None


async def collect_page_text(page: Any) -> str:
    chunks: list[str] = []
    frames = []
    with contextlib.suppress(Exception):
        frames = list(page.frames)
    if not frames:
        frames = [page.main_frame]
    for frame in frames:
        with contextlib.suppress(Exception):
            body = frame.locator("body")
            text = (await body.inner_text(timeout=1500))[:400]
            if text.strip():
                chunks.append(text)
    return "\n".join(chunks)[:2000]


async def find_qr_locator(page: Any, selectors: list[str]) -> Any | None:
    locator_css = ", ".join(selectors)
    frames = []
    with contextlib.suppress(Exception):
        frames = list(page.frames)
    if not frames:
        frames = [page.main_frame]
    for frame in frames:
        with contextlib.suppress(Exception):
            loc = frame.locator(locator_css).first
            if await loc.count() == 0:
                continue
            if await loc.is_visible(timeout=800):
                return loc
    return None


async def screenshot_qr(page: Any, selectors: list[str]) -> str | None:
    element = await find_qr_locator(page, selectors)
    if element is not None:
        with contextlib.suppress(Exception):
            return to_qr_data_url(await element.screenshot())
    with contextlib.suppress(Exception):
        return to_qr_data_url(await page.screenshot())
    return None


async def click_qr_refresh(page: Any) -> bool:
    hints = (
        "text=刷新二维码",
        "text=点击刷新",
        "[class*='qrcode-refresh']",
        "a:has-text('刷新二维码')",
        "button:has-text('刷新二维码')",
        "a:has-text('刷新')",
        "button:has-text('刷新')",
    )
    frames = []
    with contextlib.suppress(Exception):
        frames = list(page.frames)
    if not frames:
        frames = [page.main_frame]
    for frame in frames:
        for hint in hints:
            with contextlib.suppress(Exception):
                loc = frame.locator(hint).first
                if await loc.count() == 0:
                    continue
                if await loc.is_visible(timeout=400):
                    await loc.click(timeout=1500)
                    return True
    return False


def url_looks_logged_in(url: str, *, domain_keyword: str) -> bool:
    lowered = url.lower()
    if domain_keyword not in lowered:
        return False
    return "login" not in lowered and "passport" not in lowered and "signin" not in lowered


def qr_headless() -> bool:
    value = os.getenv("DINGDA_QR_HEADLESS", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def cookie_domains(cookies: list[dict[str, Any]]) -> list[str]:
    domains = {str(item.get("domain", "")).strip() for item in cookies if item.get("domain")}
    return sorted(domain for domain in domains if domain)


def has_login_cookie(cookies: list[dict[str, Any]], *, name: str, domain_keyword: str) -> bool:
    keyword = domain_keyword.lower()
    return any(
        item.get("name") == name and keyword in str(item.get("domain", "")).lower()
        for item in cookies
    )


def cookies_indicate_platform_login(
    cookies: list[dict[str, Any]],
    *,
    platform: str,
    login_cookie_name: str,
    domain_keyword: str,
) -> bool:
    if has_login_cookie(cookies, name=login_cookie_name, domain_keyword=domain_keyword):
        return True
    config = get_platform_config(platform)
    if config.sso_cookie_name and config.sso_cookie_domain_keyword:
        return has_login_cookie(
            cookies,
            name=config.sso_cookie_name,
            domain_keyword=config.sso_cookie_domain_keyword,
        )
    return False
