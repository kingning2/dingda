"""闲鱼（goofish）关键词搜索 — 系统 Camoufox 会话 + goofish_cli DOM 提取。

走系统内置的 Camoufox 浏览器会话（`browser_page_session`，Firefox 指纹 + TLS），
复用 goofish_cli 的搜索页 DOM 提取（`_EXTRACT_JS` / `_build_search_url` /
`auto_scroll`）。Cookie 优先取 DingDa 账号库注入，为空时回退 goofish_cli
Session 三级兜底（cookies.json → 本机浏览器 → 报错）。"""

from __future__ import annotations

import logging
import time
from typing import Any

from dingda_sidecar.crawlers.core.camoufox import browser_page_session
from dingda_sidecar.crawlers.goofish.browser.session import (
    prepare_cookies,
    profile_dir,
    resolve_headless,
)

logger = logging.getLogger("dingda.sidecar.goofish.search")

SEARCH_RESULT_URL = "https://www.goofish.com/search"
MAX_LIMIT = 50
HEADLESS_ENV = "DINGDA_XIANYU_SEARCH_HEADLESS"


def _first_str(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


def _item_to_offer(item: Any) -> dict[str, Any] | None:
    """把 goofish_cli DOM 提取的卡片映射为契约 offer（对齐 ChannelXianyuSearchItem）。"""
    if not isinstance(item, dict):
        return None
    url = _first_str(item.get("url"))
    if not url:
        return None

    from dingda_sidecar.crawlers.vendor.goofish_cli.commands.search.search import _item_id_from_url

    item_id = _item_id_from_url(url)
    title = _first_str(item.get("title"))
    if not item_id or not title:
        return None

    tags = [
        _first_str(item.get("condition")),
        _first_str(item.get("brand")),
    ]
    extra = _first_str(item.get("extra"))
    if extra:
        tags.extend(part.strip() for part in extra.split("|") if part.strip())
    badge = _first_str(item.get("badge"))
    if badge:
        tags.append(badge)
    tags = [tag for tag in dict.fromkeys(tags) if tag][:8]

    offer: dict[str, Any] = {
        "itemId": item_id,
        "title": title,
        "url": url,
        "price": _first_str(item.get("price")),
        "location": _first_str(item.get("location")),
        "tags": tags,
    }
    return {key: value for key, value in offer.items() if value != ""}


def _failure(status: str, keyword: str, detail: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "keyword": keyword,
        "total_before_filter": 0,
        "total": 0,
        "offers": [],
        "final_url": SEARCH_RESULT_URL,
        "detail": detail,
    }


def _fallback_cookies() -> list[dict[str, Any]]:
    """DingDa 账号库无 Cookie 时，回退 goofish_cli Session 三级兜底。"""
    try:
        from dingda_sidecar.crawlers.vendor.goofish_cli.core.browser import (
            _cookies_to_playwright,
            _load_cookies_from_session,
        )

        return _cookies_to_playwright(_load_cookies_from_session())
    except Exception:  # noqa: BLE001 — 兜底失败就无 Cookie 启动，交给页面判定
        logger.warning("闲鱼 Session 兜底取 Cookie 失败", exc_info=True)
        return []


async def fetch_search(
    keyword: str,
    *,
    account_id: str,
    cookies: list[dict[str, Any]],
    max_results: int = 20,
    headed: bool | None = None,
) -> dict[str, Any]:
    """用系统 Camoufox 会话打开闲鱼搜索页，DOM 提取并映射为统一 offer 列表。"""
    kw = keyword.strip()
    if not kw:
        raise ValueError("搜索关键词不能为空")
    if not account_id.strip():
        raise ValueError("缺少 account_id")

    from dingda_sidecar.crawlers.vendor.goofish_cli.commands.search.search import (
        _EXTRACT_JS,
        _build_search_url,
    )
    from dingda_sidecar.crawlers.vendor.goofish_cli.core.browser import auto_scroll
    from dingda_sidecar.crawlers.vendor.goofish_cli.core.errors import AuthRequiredError

    prepared = prepare_cookies(cookies)
    if not prepared:
        logger.info("闲鱼账号 Cookie 为空，回退 goofish_cli Session 三级兜底")
        prepared = _fallback_cookies()

    headless = resolve_headless(
        headed=headed,
        env_key=HEADLESS_ENV,
        default_headless=True,
    )
    url = _build_search_url(kw)
    limit = min(max(1, max_results), MAX_LIMIT)
    user_profile = profile_dir(account_id)

    started = time.perf_counter()
    actual_url = url
    try:
        async with browser_page_session(
            user_data_dir=user_profile,
            headless=headless,
            platform_name="xianyu",
            cookies=prepared or None,
        ) as page:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            await auto_scroll(page, times=2)
            payload = await page.evaluate(_EXTRACT_JS, limit)
            actual_url = str(page.url)
    except AuthRequiredError as error:
        return _failure("not_logged_in", kw, f"闲鱼需要登录：{error}")
    except Exception as error:  # noqa: BLE001
        logger.exception("闲鱼搜索异常 keyword=%s", kw)
        return _failure("error", kw, f"闲鱼搜索失败: {error}")

    final_url = actual_url
    if not isinstance(payload, dict):
        return _failure("error", kw, "搜索页返回结构非预期")

    items = payload.get("items") or []
    if not items and payload.get("requiresAuth"):
        return _failure("not_logged_in", kw, "www.goofish.com 搜索结果页要求登录，Cookie 可能失效")
    if not items and payload.get("blocked"):
        return _failure("error", kw, "搜索页返回验证码/安全验证（触发风控），稍后重试或换账号")
    if not items and not payload.get("empty"):
        preview = str(payload.get("bodyPreview") or "")[:200]
        return _failure(
            "error",
            kw,
            f"未在搜索页上解析到任何卡片，可能 DOM 结构已变。页面文案预览：{preview!r}",
        )

    offers = [offer for offer in (_item_to_offer(item) for item in items) if offer is not None]
    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    logger.info(
        "闲鱼搜索完成 keyword=%s total=%s duration_ms=%s",
        kw,
        len(offers),
        duration_ms,
    )
    return {
        "ok": bool(offers),
        "status": "success" if offers else "empty",
        "keyword": kw,
        "total_before_filter": len(items),
        "total": len(offers),
        "offers": offers,
        "final_url": final_url,
        "detail": f"找到 {len(offers)} 条结果（Camoufox DOM）",
    }
