"""1688 关键词搜索 — Camoufox 指纹浏览器 + MTOP getOfferList 拦截。

打开首页或搜索页，捕获 MTOP 响应并解析为统一 offer 列表；支持有头超时加长。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from crawlers.alibaba.browser.session import (
    looks_blocked,
    prepare_cookies,
    profile_dir,
    resolve_headless,
)
from crawlers.alibaba.search.mtop import (
    SEARCH_APP_ID,
    parse_offer_items_from_mtop_text,
    read_search_mtop_request_meta,
)
from crawlers.core.camoufox import close_renew_session, launch_renew_context
from crawlers.core.playwright_common import clear_profile_locks

logger = logging.getLogger("dingda.sidecar.ali1688.search")

SEARCH_WARMUP_URL = "https://www.1688.com/"
DEFAULT_TIMEOUT_MS = 15_000
HEADED_TIMEOUT_MS = 180_000

_HOMEPAGE_SEARCH_INPUT = (
    "input[name='keywords']",
    "input[name='keyword']",
    "input[type='search']",
    "input[placeholder*='搜索']",
    "input[placeholder*='找']",
)


def encode_gbk_percent(keyword: str) -> str:
    return "".join(f"%{byte:02X}" for byte in keyword.encode("gbk", errors="replace"))


def build_search_url(keyword: str) -> str:
    return f"https://s.1688.com/selloffer/offer_search.htm?keywords={encode_gbk_percent(keyword)}"


class _SearchOfferCapture:
    def __init__(self, page: Any, *, target_page: int = 1) -> None:
        self._page = page
        self._target_page = target_page
        self._offers: list[dict[str, Any]] = []
        self._disposed = False

        async def on_response(response: Any) -> None:
            if self._disposed:
                return
            url = str(response.url)
            meta = read_search_mtop_request_meta(url)
            if meta:
                if meta.get("appId") != SEARCH_APP_ID:
                    return
                if meta.get("method") != "getOfferList":
                    return
                if (meta.get("beginPage") or 1) != self._target_page:
                    return
            elif SEARCH_APP_ID not in url and "wirelessrecommend.recommend" not in url:
                return
            with contextlib.suppress(Exception):
                parsed = parse_offer_items_from_mtop_text(await response.text())
                if parsed:
                    self._offers = parsed

        def handler(response: Any) -> None:
            asyncio.create_task(on_response(response))

        self._handler = handler
        page.on("response", handler)

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        with contextlib.suppress(Exception):
            self._page.off("response", self._handler)

    @property
    def offers(self) -> list[dict[str, Any]]:
        return self._offers


async def _find_first_visible(page: Any, selectors: tuple[str, ...]) -> Any | None:
    for selector in selectors:
        with contextlib.suppress(Exception):
            loc = page.locator(selector).first
            if await loc.count() == 0:
                continue
            if await loc.is_visible(timeout=800):
                return loc
    return None


async def _submit_search_from_homepage(page: Any, keyword: str) -> bool:
    input_loc = await _find_first_visible(page, _HOMEPAGE_SEARCH_INPUT)
    if input_loc is None:
        return False
    before = str(page.url)
    with contextlib.suppress(Exception):
        await input_loc.click(timeout=2000)
        await page.keyboard.press("Control+A")
        await page.keyboard.type(keyword, delay=60)
        await page.keyboard.press("Enter")
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if page.url != before and "1688.com" in page.url:
                return True
            await page.wait_for_timeout(200)
    return False


async def fetch_search(
    keyword: str,
    *,
    account_id: str,
    cookies: list[dict[str, Any]],
    max_results: int = 20,
    headed: bool | None = None,
) -> dict[str, Any]:
    """用 Camoufox/Chromium 指纹 profile 搜索 1688。"""
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
        env_key="DINGDA_1688_SEARCH_HEADLESS",
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
            platform_name="ali1688",
        )
        with contextlib.suppress(Exception):
            await context.add_cookies(prepared)

        page = context.pages[0] if context.pages else await context.new_page()
        capture = _SearchOfferCapture(page, target_page=1)

        logger.info(
            "1688 搜索开始 account=%s engine=%s headless=%s keyword=%s",
            account_id,
            engine,
            headless,
            kw,
        )
        with contextlib.suppress(Exception):
            await page.goto(SEARCH_WARMUP_URL, wait_until="domcontentloaded", timeout=20_000)
            await page.wait_for_timeout(1500)

        search_url = build_search_url(kw)
        submitted = await _submit_search_from_homepage(page, kw)
        if not submitted:
            logger.info("1688 首页搜索框不可用，直连 %s", search_url[:120])
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if capture.offers:
                break
            if looks_blocked(str(page.url)):
                break
            await page.wait_for_timeout(300)

        if not capture.offers and not looks_blocked(str(page.url)):
            logger.warning("1688 首次搜索无 MTOP 结果，重试 warmup + 直连")
            with contextlib.suppress(Exception):
                await page.goto(SEARCH_WARMUP_URL, wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(3500)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
            retry_deadline = time.monotonic() + 15
            while time.monotonic() < retry_deadline:
                if capture.offers:
                    break
                await page.wait_for_timeout(300)

        capture.dispose()
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
                "detail": "1688 会话失效或触发风控，请在弹出的指纹浏览器中完成登录/滑块后重试",
            }

        offers = capture.offers[: max(1, max_results)]
        return {
            "ok": bool(offers),
            "status": "success" if offers else "empty",
            "keyword": kw,
            "total_before_filter": len(capture.offers),
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
