"""单浏览器多标签页批量探针 / Token 续期。

同一 Chromium 进程内为每个账号创建独立 BrowserContext（隔离 Cookie），
并行打开各平台首页，避免「一个网站一个浏览器」。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Any

from dingda_sidecar.crawlers.alibaba.browser.session import looks_blocked, prepare_cookies
from dingda_sidecar.crawlers.core.login.helpers import (
    cookies_indicate_platform_login,
    url_looks_logged_in,
)
from dingda_sidecar.crawlers.core.platform_config import get_platform_config, normalize_platform
from dingda_sidecar.crawlers.core.playwright_common import (
    LAUNCH_ARGS,
    apply_stealth,
    async_playwright,
    clear_profile_locks,
)
from dingda_sidecar.crawlers.factory import create_channel

logger = logging.getLogger("dingda.sidecar.batch-session")

BATCH_PROFILE_DIR = Path.cwd() / "browser_data" / "batch_sessions"
DEFAULT_TIMEOUT_MS = 30_000


def _headless() -> bool:
    value = os.getenv("DINGDA_BATCH_SESSION_HEADLESS", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _filter_platform_cookies(
    cookies: list[dict[str, Any]], domain_keyword: str
) -> list[dict[str, Any]]:
    keyword = domain_keyword.lower()
    return [cookie for cookie in cookies if keyword in str(cookie.get("domain") or "").lower()]


def _online_from_jar(
    jar: list[dict[str, Any]],
    *,
    platform: str,
    login_cookie_name: str,
    domain_keyword: str,
    final_url: str,
) -> bool:
    if platform == "ali1688":
        blocked = looks_blocked(final_url)
        cookie_ok = cookies_indicate_platform_login(
            jar,
            platform=platform,
            login_cookie_name=login_cookie_name,
            domain_keyword=domain_keyword,
        )
        url_ok = url_looks_logged_in(final_url, domain_keyword="1688.com")
        return not blocked and (cookie_ok or url_ok)
    if platform == "xiaohongshu":
        return cookies_indicate_platform_login(
            jar,
            platform=platform,
            login_cookie_name=login_cookie_name,
            domain_keyword=domain_keyword,
        ) and any(cookie.get("name") == "a1" for cookie in jar)
    if platform == "xianyu":
        return cookies_indicate_platform_login(
            jar,
            platform=platform,
            login_cookie_name=login_cookie_name,
            domain_keyword=domain_keyword,
        ) and any(cookie.get("name") == "_m_h5_tk" for cookie in jar)
    return cookies_indicate_platform_login(
        jar,
        platform=platform,
        login_cookie_name=login_cookie_name,
        domain_keyword=domain_keyword,
    )


async def _process_target(
    browser: Any,
    *,
    account_id: str,
    platform: str,
    cookies: list[dict[str, Any]],
    refresh: bool,
) -> dict[str, Any]:
    platform = normalize_platform(platform)
    config = get_platform_config(platform)
    prepared = prepare_cookies(cookies)
    if not prepared:
        return {
            "account_id": account_id,
            "platform": platform,
            "ok": False,
            "online": False,
            "status": "error",
            "detail": "无有效 Cookie",
            "cookies": None,
        }

    browser_cfg = create_channel(platform).browser()
    proxy = browser_cfg.resolve_proxy()
    context = await browser.new_context(
        user_agent=browser_cfg.resolve_user_agent(),
        viewport={"width": 1280, "height": 720},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        **({"proxy": proxy} if proxy else {}),
    )
    page = None
    try:
        await apply_stealth(context, logger)
        await browser_cfg.apply_anti_detect(context, logger)
        with contextlib.suppress(Exception):
            await context.add_cookies(prepared)
        page = await context.new_page()
        logger.info("batch session 开标签 account=%s platform=%s", account_id, platform)
        await page.goto(
            config.home_url,
            wait_until="domcontentloaded",
            timeout=DEFAULT_TIMEOUT_MS,
        )
        await page.wait_for_timeout(2500 if refresh else 1500)

        final_url = str(page.url)
        jar = await context.cookies()
        online = _online_from_jar(
            jar,
            platform=platform,
            login_cookie_name=config.login_cookie_name,
            domain_keyword=config.cookie_domain_keyword,
            final_url=final_url,
        )
        exported = (
            _filter_platform_cookies(jar, config.cookie_domain_keyword)
            if refresh and online
            else None
        )
        return {
            "account_id": account_id,
            "platform": platform,
            "ok": True,
            "online": online,
            "status": "online" if online else "offline",
            "detail": f"final_url={final_url[:120]}",
            "cookies": exported,
        }
    except Exception as error:  # noqa: BLE001
        logger.exception("batch session 标签失败 account=%s", account_id)
        return {
            "account_id": account_id,
            "platform": platform,
            "ok": False,
            "online": False,
            "status": "error",
            "detail": str(error),
            "cookies": None,
        }
    finally:
        with contextlib.suppress(Exception):
            if page is not None:
                await page.close()
        with contextlib.suppress(Exception):
            await context.close()


async def batch_sessions(
    targets: list[dict[str, Any]],
    *,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """单浏览器多标签页批量探针 / 续期。"""
    if not targets:
        return []
    if async_playwright is None:
        raise RuntimeError("playwright 未安装")

    headless = _headless()
    BATCH_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    clear_profile_locks(BATCH_PROFILE_DIR)

    playwright = None
    browser = None
    started = time.perf_counter()
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=headless,
            args=list(LAUNCH_ARGS),
            ignore_default_args=["--enable-automation"],
        )
        logger.info(
            "batch session 单浏览器启动 tabs=%s refresh=%s headless=%s",
            len(targets),
            refresh,
            headless,
        )
        jobs = [
            _process_target(
                browser,
                account_id=str(target.get("account_id") or "").strip(),
                platform=str(target.get("platform") or "xianyu"),
                cookies=target.get("cookies") if isinstance(target.get("cookies"), list) else [],
                refresh=refresh,
            )
            for target in targets
            if str(target.get("account_id") or "").strip()
        ]
        results = await asyncio.gather(*jobs)
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info("batch session 完成 tabs=%s duration_ms=%s", len(results), duration_ms)
        return list(results)
    finally:
        if browser is not None:
            with contextlib.suppress(Exception):
                await browser.close()
        if playwright is not None:
            with contextlib.suppress(Exception):
                await playwright.stop()
