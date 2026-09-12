"""闲鱼登录与扫码过程中的风控恢复。

职责：
    经 BrowserManager 开页 → 自动滑块 → 有头人工兜底；导出续期后的 cookie 供登录流程使用。

设计说明：
    - 平台：闲鱼（xianyu）
    - 调用方：XianyuChannel 扫码状态机；不直接供 Tool / Agent
    - Browser 仅作通用开页/滑块能力，不含商品等业务逻辑
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable

from browser.context import serialize_cookies
from browser.manager import BrowserManager
from contracts.browser_port import LaunchOptions
from channels.xianyu.slider import (
    auto_slider_enabled,
    clear_risk_cookies,
    has_x5sec,
    try_solve_slider,
)
from channels.xianyu.login import HOME_URL
from channels.xianyu.cookies import to_browser_cookies
from channels.xianyu.risk import page_is_punish

logger = logging.getLogger("dingda.channel.xianyu.renew")

DEFAULT_TIMEOUT_SECS = 180
_REQUIRED = ("_m_h5_tk", "unb", "cookie2")

_RENEW_COOKIE_DOMAINS = (
    "goofish.com",
    "taobao.com",
    "alibaba.com",
    "alipay.com",
    "mmstat.com",
    "alicdn.com",
)
_PREFERRED_COOKIE_DOMAINS = ("goofish.com", "taobao.com")


def _safe_account_dir(account_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", account_id.strip()) or "unknown"
    return cleaned[:80]


def _profile_dir(account_id: str) -> Path:
    return Path.home() / ".dingda" / "v2" / "browser_profiles" / _safe_account_dir(account_id)


def _domain_rank(domain: str) -> int:
    lowered = (domain or "").lower()
    for index, preferred in enumerate(_PREFERRED_COOKIE_DOMAINS):
        if preferred in lowered:
            return index
    return 100


def _is_renew_domain(domain: str) -> bool:
    lowered = (domain or "").lower()
    return any(item in lowered for item in _RENEW_COOKIE_DOMAINS)


def _dedupe_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        if not name or not cookie.get("value"):
            continue
        domain = str(cookie.get("domain") or "")
        previous = best.get(name)
        if previous is None or _domain_rank(domain) < _domain_rank(str(previous.get("domain") or "")):
            best[name] = cookie
    return list(best.values())


def _filter_export_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = [
        cookie
        for cookie in cookies
        if _is_renew_domain(str(cookie.get("domain") or ""))
        or str(cookie.get("name") or "")
        in {
            "unb",
            "_m_h5_tk",
            "_m_h5_tk_enc",
            "cookie2",
            "cna",
            "x5sec",
            "XSRF-TOKEN",
            "sgcookie",
            "tfstk",
            "isg",
        }
    ]
    if not filtered:
        filtered = list(cookies)
    return _dedupe_cookies(filtered)


def _merge_prepared_with_browser(
    prepared: list[dict[str, Any]],
    browser_cookies: list[dict[str, Any]],
) -> dict[str, str]:
    merged: dict[str, dict[str, Any]] = {}
    for cookie in prepared:
        name = str(cookie.get("name") or "").strip()
        if name and cookie.get("value"):
            merged[name] = cookie
    for cookie in _filter_export_cookies(browser_cookies):
        name = str(cookie.get("name") or "").strip()
        if name and cookie.get("value"):
            merged[name] = cookie
    return {name: str(item["value"]) for name, item in merged.items() if item.get("value")}


def _session_ready(cookie_map: dict[str, str]) -> bool:
    return all(cookie_map.get(key) for key in _REQUIRED)


def _looks_logged_in(url: str, cookie_map: dict[str, str]) -> bool:
    has_login = bool(cookie_map.get("unb"))
    has_tk = bool(cookie_map.get("_m_h5_tk"))
    if has_login and has_tk and any(name.startswith("x5") for name in cookie_map):
        return True
    blocked = page_is_punish(url) or "passport" in (url or "").lower()
    return has_login and has_tk and not blocked


def _cookies_as_export_dicts(cookies: dict[str, str] | None) -> list[dict[str, Any]]:
    """Channel Cookie → 可与浏览器导出合并的字典列表。"""
    from browser.context import cookies_to_playwright

    return list(cookies_to_playwright(to_browser_cookies(cookies or {})))


async def _export_after_slider(
    *,
    page: Any,
    context: Any,
    account_id: str,
    prepared: list[dict[str, Any]],
) -> tuple[bool, str, dict[str, str] | None]:
    await page.wait_for_timeout(500)
    for attempt in range(1, 4):
        current = (page.url or "").lower()
        on_goofish = "goofish.com" in current and "passport" not in current
        if not on_goofish:
            logger.info("滑块后回访闲鱼首页 account=%s attempt=%s", account_id, attempt)
            try:
                await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=40_000)
                await page.wait_for_timeout(3000)
            except Exception as exc:
                logger.warning("回访闲鱼首页失败 account=%s: %s", account_id, exc)
                continue

        raw = serialize_cookies(await context.cookies())
        exported = _merge_prepared_with_browser(prepared, raw)
        if _session_ready(exported):
            logger.info("滑块后已导出有效 Cookie account=%s", account_id)
            return True, "自动滑块通过，已导出 Cookie", exported

    raw = serialize_cookies(await context.cookies())
    exported = _merge_prepared_with_browser(prepared, raw)
    if _session_ready(exported):
        return True, "自动滑块通过，已导出 Cookie", exported
    return False, "滑块疑似通过但未能导出有效 Cookie", None


async def _run_camoufox_session(
    *,
    prepared: list[dict[str, Any]],
    account_id: str,
    target: str,
    timeout_secs: int,
    headless: bool,
    try_auto: bool,
    on_status: Callable[[str], None] | None = None,
) -> tuple[bool, str, dict[str, str] | None]:
    user_data_dir = _profile_dir(account_id) / "camoufox"
    manager = BrowserManager("camoufox")
    page_wrap = None
    try:
        port = await manager.start(
            LaunchOptions(headless=headless, user_data_dir=user_data_dir)
        )
        injected = to_browser_cookies(
            {str(c["name"]): str(c["value"]) for c in prepared if c.get("name") and c.get("value")}
        )
        page_wrap = await port.open(cookies=injected or None)
        page = page_wrap.raw
        context = page_wrap.context
        logger.info(
            "开始 Camoufox 风控恢复 account=%s headless=%s auto_slider=%s url=%s",
            account_id,
            headless,
            try_auto,
            target[:120],
        )
        await page.goto(target, wait_until="domcontentloaded", timeout=40_000)
        await page.wait_for_timeout(1500)
        await clear_risk_cookies(context)

        if try_auto:
            on_status and on_status("检测到风控，正在自动过滑块…")
            ok, detail = await try_solve_slider(
                page,
                context,
                max_retries=3,
                prefer_page_mouse=True,
            )
            logger.info("Camoufox 自动滑块结果 account=%s ok=%s detail=%s", account_id, ok, detail)
            if ok:
                return await _export_after_slider(
                    page=page,
                    context=context,
                    account_id=account_id,
                    prepared=prepared,
                )
            return False, detail or "自动滑块未通过", None

        on_status and on_status("自动滑块未通过，已打开 Camoufox 窗口，请完成验证")
        logger.info("等待人工完成滑块 account=%s（已打开 Camoufox 窗口）", account_id)

        deadline = time.monotonic() + max(15, timeout_secs)
        last_detail = "请在弹出的 Camoufox 窗口完成滑块验证"

        while time.monotonic() < deadline:
            raw = serialize_cookies(await context.cookies())
            exported = _merge_prepared_with_browser(prepared, raw)
            url = page.url or ""
            if _looks_logged_in(url, exported):
                if page_is_punish(url) and not has_x5sec(raw):
                    last_detail = "仍在验证码页，请完成滑块"
                    await page.wait_for_timeout(1500)
                    continue
                if "goofish.com" not in url.lower():
                    with contextlib.suppress(Exception):
                        await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=40_000)
                        await page.wait_for_timeout(2000)
                    raw = serialize_cookies(await context.cookies())
                    exported = _merge_prepared_with_browser(prepared, raw)
                if _session_ready(exported):
                    logger.info("Camoufox 人工验证成功 account=%s", account_id)
                    return True, "浏览器续期成功，已导出 Cookie", exported
                last_detail = "已登录但会话尚未稳定，继续等待首页"
            await page.wait_for_timeout(1500)

        return False, f"浏览器续期超时：{last_detail}", None
    except Exception as exc:
        phase = "自动滑块" if try_auto else "人工验证"
        logger.exception("Camoufox %s失败 account=%s: %s", phase, account_id, exc)
        return False, f"Camoufox {phase}失败: {exc}", None
    finally:
        if page_wrap is not None:
            with contextlib.suppress(Exception):
                await page_wrap.close()
        await manager.stop()


async def _recover_async(
    cookies: dict[str, str] | None,
    *,
    account_id: str,
    punish_url: str | None,
    timeout_secs: int,
    on_status: Callable[[str], None] | None = None,
) -> tuple[bool, str, dict[str, str] | None]:
    prepared = _cookies_as_export_dicts(cookies)
    punish = (punish_url or "").strip()
    target = punish or HOME_URL

    if auto_slider_enabled():
        ok, detail, exported = await _run_camoufox_session(
            prepared=prepared,
            account_id=account_id,
            target=target,
            timeout_secs=min(60, timeout_secs),
            headless=True,
            try_auto=True,
            on_status=on_status,
        )
        if ok and exported:
            return ok, detail, exported
        logger.warning("Camoufox 自动滑块未通过，回退有头 Camoufox account=%s detail=%s", account_id, detail)

    return await _run_camoufox_session(
        prepared=prepared,
        account_id=account_id,
        target=target,
        timeout_secs=timeout_secs,
        headless=False,
        try_auto=False,
        on_status=on_status,
    )


def renew(
    cookies: dict[str, str] | None = None,
    *,
    account_id: str = "qr-recover",
    punish_url: str | None = None,
    timeout_secs: int = DEFAULT_TIMEOUT_SECS,
    on_status: Callable[[str], None] | None = None,
) -> tuple[bool, str, dict[str, str] | None]:
    """扫码失败或触发风控时：无头自动滑块 → 有头人工兜底。"""
    return asyncio.run(
        _recover_async(
            cookies,
            account_id=account_id,
            punish_url=punish_url,
            timeout_secs=timeout_secs,
            on_status=on_status,
        )
    )
