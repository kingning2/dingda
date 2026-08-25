"""1688 登录态 Playwright 探针（对齐 1688-cli verifyOnline）。"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from crawlers.alibaba.browser.session import (
    looks_blocked,
    prepare_cookies,
    profile_dir,
    resolve_headless,
)
from crawlers.core.camoufox import close_renew_session, launch_renew_context
from crawlers.core.login.helpers import cookies_indicate_platform_login, url_looks_logged_in
from crawlers.core.platform_config import get_platform_config
from crawlers.core.playwright_common import clear_profile_locks

logger = logging.getLogger("dingda.sidecar.ali1688.login.probe")

PROBE_URL = "https://myalibaba.1688.com/"
DEFAULT_TIMEOUT_MS = 25_000


async def verify_login_online(
    *,
    account_id: str,
    cookies: list[dict[str, Any]],
    headed: bool | None = None,
) -> dict[str, Any]:
    """用指纹浏览器加载 Cookie 并访问 1688 工作台，判断是否仍在线。"""
    if not account_id.strip():
        raise ValueError("缺少 account_id")
    prepared = prepare_cookies(cookies)
    if not prepared:
        raise ValueError("缺少有效 Cookie")

    config = get_platform_config("ali1688")
    headless = resolve_headless(
        headed=headed,
        env_key="DINGDA_1688_PROBE_HEADLESS",
        default_headless=True,
    )
    user_profile = profile_dir(account_id)
    user_profile.mkdir(parents=True, exist_ok=True)
    clear_profile_locks(user_profile)

    playwright = None
    browser_or_cm = None
    context = None
    engine = "chromium"
    page = None
    try:
        playwright, browser_or_cm, context, engine = await launch_renew_context(
            user_data_dir=user_profile,
            headless=headless,
            platform_name="ali1688",
        )
        with contextlib.suppress(Exception):
            await context.add_cookies(prepared)

        page = context.pages[0] if context.pages else await context.new_page()
        logger.info(
            "1688 登录探针开始 account=%s engine=%s headless=%s",
            account_id,
            engine,
            headless,
        )
        await page.goto(PROBE_URL, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        await page.wait_for_timeout(1500)

        final_url = str(page.url)
        jar: list[dict[str, Any]] = []
        with contextlib.suppress(Exception):
            jar = await context.cookies()

        cookie_ok = cookies_indicate_platform_login(
            jar,
            platform="ali1688",
            login_cookie_name=config.login_cookie_name,
            domain_keyword=config.cookie_domain_keyword,
        )
        url_ok = url_looks_logged_in(final_url, domain_keyword="1688.com")
        blocked = looks_blocked(final_url)
        online = not blocked and (cookie_ok or url_ok)

        status = "online" if online else "offline"
        detail = (
            f"final_url={final_url[:120]} cookie_ok={cookie_ok} url_ok={url_ok} blocked={blocked}"
        )
        logger.info(
            "1688 登录探针完成 account=%s online=%s status=%s",
            account_id,
            online,
            status,
        )
        return {
            "ok": True,
            "online": online,
            "status": status,
            "final_url": final_url,
            "detail": detail,
        }
    finally:
        with contextlib.suppress(Exception):
            if page and not headless:
                await page.wait_for_timeout(500)
        await close_renew_session(
            playwright=playwright,
            browser_or_cm=browser_or_cm,
            context=context,
            engine=engine,
        )
