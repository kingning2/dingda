"""1688 关键词搜索 — Camoufox 指纹浏览器 + MTOP getOfferList 拦截。

打开首页或搜索页，捕获 MTOP 响应并解析为统一 offer 列表；支持有头超时加长。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from dingda_sidecar.crawlers.alibaba.browser.session import (
    looks_blocked,
    prepare_cookies,
    profile_dir,
    resolve_headless,
)
from dingda_sidecar.crawlers.alibaba.search.mtop import (
    SEARCH_APP_ID,
    parse_offer_items_from_mtop_text,
    read_search_mtop_request_meta,
)
from dingda_sidecar.crawlers.core.camoufox import close_renew_session, launch_renew_context
from dingda_sidecar.crawlers.core.playwright_common import clear_profile_locks
from dingda_sidecar.crawlers.core.slider import (
    auto_slider_enabled,
    clear_risk_cookies,
    try_solve_slider,
)

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


_RISK_URL_MARKERS = (
    "/punish",
    "x5secdata=",
    "_____tmd_____",
    "captcha",
    "sec.1688.com",
)


def _risk_url(url: str) -> bool:
    lowered = (url or "").lower()
    return any(marker in lowered for marker in _RISK_URL_MARKERS)


async def _goto_search(page: Any, search_url: str) -> None:
    with contextlib.suppress(Exception):
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)


async def _wait_search_response(page: Any, capture: _SearchOfferCapture, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if capture.offers:
            return
        if looks_blocked(str(page.url)):
            return
        await page.wait_for_timeout(300)


async def _solve_risk_slider(page: Any, context: Any, *, engine: str, account_id: str) -> bool:
    """命中风控页时自动拖滑块；正常页面直接返回 False。

    复用阿里系滑块求解器（拟人轨迹轮换）；Camoufox 无 CDP，走 page.mouse。
    求解前先清 risk cookies，避免旧 x5sec 形成"刷新→再 punish"死循环。
    """
    if not auto_slider_enabled() or not _risk_url(str(page.url)):
        return False
    logger.info("1688 命中风控页，尝试自动滑块 url=%s", str(page.url)[:160])
    await clear_risk_cookies(context)
    ok, detail = await try_solve_slider(
        page, context, max_retries=3, prefer_page_mouse=(engine == "camoufox")
    )
    logger.info(
        "1688 自动滑块结果 account=%s ok=%s detail=%s url=%s",
        account_id,
        ok,
        detail,
        str(page.url or "")[:160],
    )
    return ok


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
        default_headless=True,
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
            await _goto_search(page, search_url)

        await _wait_search_response(page, capture, timeout_ms / 1000)

        # 直连命中风控：自动过滑块后重放搜索（punish 页拿不到 MTOP 响应）
        if not capture.offers and await _solve_risk_slider(
            page, context, engine=engine, account_id=account_id
        ):
            await _goto_search(page, search_url)
            await _wait_search_response(page, capture, 15.0)

        if not capture.offers and not looks_blocked(str(page.url)):
            logger.warning("1688 首次搜索无 MTOP 结果，重试 warmup + 直连")
            with contextlib.suppress(Exception):
                await page.goto(SEARCH_WARMUP_URL, wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(3500)
            await _goto_search(page, search_url)
            await _wait_search_response(page, capture, 15.0)
            # 重试直连仍可能落入风控页：再给一次滑块机会
            if not capture.offers and await _solve_risk_slider(
                page, context, engine=engine, account_id=account_id
            ):
                await _goto_search(page, search_url)
                await _wait_search_response(page, capture, 15.0)

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
                "detail": "1688 会话失效或滑块未通过，请在弹出的浏览器中完成验证后重试",
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
