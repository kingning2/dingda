"""闲鱼关键词搜索（Camoufox/Chromium + MTOP idlemtopsearch 拦截）。"""

from __future__ import annotations

import contextlib
import logging
from typing import Any
from urllib.parse import urlencode

from crawlers.core.camoufox import close_renew_session, launch_renew_context
from crawlers.core.playwright_common import clear_profile_locks
from crawlers.xianyu.browser.session import (
    looks_blocked,
    prepare_cookies,
    profile_dir,
    resolve_headless,
)
from crawlers.xianyu.search.mtop import is_search_results_response, parse_search_items

logger = logging.getLogger("dingda.sidecar.xianyu.search")

GOOFISH_HOME_URL = "https://www.goofish.com/"
DEFAULT_TIMEOUT_MS = 15_000
HEADED_TIMEOUT_MS = 180_000


def build_search_url(keyword: str) -> str:
    return f"{GOOFISH_HOME_URL}search?{urlencode({'q': keyword})}"


async def fetch_search(
    keyword: str,
    *,
    account_id: str,
    cookies: list[dict[str, Any]],
    max_results: int = 20,
    headed: bool | None = None,
) -> dict[str, Any]:
    """用 Camoufox/Chromium 指纹 profile 搜索闲鱼。"""
    kw = keyword.strip()
    if not kw:
        raise ValueError("搜索关键词不能为空")
    if not account_id.strip():
        raise ValueError("缺少 account_id")
    prepared = prepare_cookies(cookies)
    if not prepared:
        raise ValueError("缺少有效 Cookie")

    headless = resolve_headless(
        headed=headed,
        env_key="DINGDA_XIANYU_SEARCH_HEADLESS",
        default_headless=False,
    )
    timeout_ms = HEADED_TIMEOUT_MS if not headless else DEFAULT_TIMEOUT_MS
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
            platform_name="xianyu",
        )
        with contextlib.suppress(Exception):
            await context.add_cookies(prepared)

        page = context.pages[0] if context.pages else await context.new_page()
        logger.info(
            "闲鱼搜索开始 account=%s engine=%s headless=%s keyword=%s",
            account_id,
            engine,
            headless,
            kw,
        )

        with contextlib.suppress(Exception):
            await page.goto(GOOFISH_HOME_URL, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(1200)

        search_url = build_search_url(kw)
        search_response = None
        try:
            async with page.expect_response(
                is_search_results_response, timeout=timeout_ms
            ) as response_info:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
            search_response = await response_info.value
        except Exception as error:  # noqa: BLE001
            logger.warning("闲鱼搜索 API 等待超时: %s", error)

        final_url = str(page.url)
        if looks_blocked(final_url):
            return {
                "ok": False,
                "status": "not_logged_in",
                "keyword": kw,
                "total_before_filter": 0,
                "total": 0,
                "offers": [],
                "final_url": final_url,
                "detail": "闲鱼会话失效或需登录，请在弹出的浏览器中完成登录/滑块后重试",
            }

        items: list[dict[str, Any]] = []
        if search_response is not None:
            with contextlib.suppress(Exception):
                if search_response.ok:
                    payload = await search_response.json()
                    if isinstance(payload, dict):
                        items = parse_search_items(payload)

        if not items:
            baxia = page.locator("div.baxia-dialog-mask")
            middleware = page.locator("div.J_MIDDLEWARE_FRAME_WIDGET")
            for locator, label in ((baxia, "baxia-dialog"), (middleware, "middleware")):
                with contextlib.suppress(Exception):
                    if await locator.is_visible(timeout=1500):
                        return {
                            "ok": False,
                            "status": "error",
                            "keyword": kw,
                            "total_before_filter": 0,
                            "total": 0,
                            "offers": [],
                            "final_url": final_url,
                            "detail": (
                                f"闲鱼触发风控验证（{label}），请稍后重试或在有头浏览器中完成验证"
                            ),
                        }

        offers = items[: max(1, max_results)]
        return {
            "ok": bool(offers),
            "status": "success" if offers else "empty",
            "keyword": kw,
            "total_before_filter": len(items),
            "total": len(offers),
            "offers": offers,
            "final_url": final_url,
            "detail": f"找到 {len(offers)} 条结果（engine={engine}）",
        }
    finally:
        with contextlib.suppress(Exception):
            if page and not headless:
                await page.wait_for_timeout(800)
        await close_renew_session(
            playwright=playwright,
            browser_or_cm=browser_or_cm,
            context=context,
            engine=engine,
        )
