"""小红书关键词搜索 — 走 vendored xhs-cli（`XhsClient`，系统 Camoufox）。

用 `XhsClient.search_notes` 导航真实页面读 `__INITIAL_STATE__`（跑在系统 Camoufox
上，patch 见 VENDOR.md），Cookie 由 DingDa 账号库注入；`XhsClient` 的笔记详情、
评论、用户等方法随包可用。

环境变量：
- ``DINGDA_PLUGINS_DIR``：插件目录（Camoufox 定位）
- ``DINGDA_XIAOHONGSHU_SEARCH_HEADLESS``：无头开关，默认无头
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

logger = logging.getLogger("dingda.sidecar.xiaohongshu.search")

SEARCH_RESULT_URL = "https://www.xiaohongshu.com/search_result"


def _first_str(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""


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


def _result(
    kw: str,
    *,
    feeds: list[Any],
    offers: list[dict[str, Any]],
    final_url: str,
    engine: str,
) -> dict[str, Any]:
    return {
        "ok": bool(offers),
        "status": "success" if offers else "empty",
        "keyword": kw,
        "total_before_filter": len(feeds),
        "total": len(offers),
        "offers": offers,
        "final_url": final_url,
        "detail": f"找到 {len(offers)} 条笔记（{engine}）",
    }


def _feed_to_offer(feed: Any) -> dict[str, Any] | None:
    """把搜索 feeds 条目（`__INITIAL_STATE__`）映射为契约 offer。"""
    if not isinstance(feed, dict):
        return None
    note_id = _first_str(feed.get("id"))
    if not note_id:
        return None

    card = feed.get("noteCard") if isinstance(feed.get("noteCard"), dict) else {}
    title = _first_str(card.get("displayTitle"))
    if not title:
        return None

    xsec = _first_str(feed.get("xsecToken"))
    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    if xsec:
        url = f"{url}?xsec_token={xsec}&xsec_source=pc_search"

    user = card.get("user") if isinstance(card.get("user"), dict) else {}
    interact = card.get("interactInfo") if isinstance(card.get("interactInfo"), dict) else {}
    cover = card.get("cover") if isinstance(card.get("cover"), dict) else {}
    image = _first_str(cover.get("url"))
    if not image and isinstance(cover.get("infoList"), list):
        for info in cover["infoList"]:
            if isinstance(info, dict):
                image = _first_str(info.get("url"))
                if image:
                    break

    offer: dict[str, Any] = {
        "offerId": note_id,
        "title": title,
        "supplier": _first_str(user.get("nickname"), user.get("nickName")),
        "turnover": _first_str(interact.get("likedCount")),
        "url": url,
        "image": image,
    }
    return {key: value for key, value in offer.items() if value != ""}


def _cookies_to_name_value(cookies: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in cookies or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        value = str(raw.get("value") or "").strip()
        if name and value:
            out[name] = value
    return out


def _resolve_headless(headed: bool | None) -> bool:
    if headed is not None:
        return not headed
    value = os.getenv("DINGDA_XIAOHONGSHU_SEARCH_HEADLESS", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _search_via_xhs_client_sync(kw: str, cookie_map: dict[str, str], headless: bool) -> list[Any]:
    """同步跑 vendored XhsClient.search_notes（复用系统 Camoufox）。"""
    from dingda_sidecar.crawlers.core.camoufox import resolve_camoufox_executable_with_version
    from dingda_sidecar.crawlers.vendor.xhs_cli.client import XhsClient

    exe, ff_version = resolve_camoufox_executable_with_version()
    with XhsClient(
        cookie_map,
        headless=headless,
        executable_path=exe,
        ff_version=ff_version,
    ) as client:
        result = client.search_notes(kw)
    return result if isinstance(result, list) else []


async def fetch_search(
    keyword: str,
    *,
    account_id: str,
    cookies: list[dict[str, Any]],
    max_results: int = 20,
    headed: bool | None = None,
) -> dict[str, Any]:
    """vendored XhsClient 搜索小红书（系统 Camoufox）。"""
    del account_id  # XhsClient 用注入的 Cookie，不需要 profile 目录
    kw = keyword.strip()
    if not kw:
        raise ValueError("搜索关键词不能为空")

    cookie_map = _cookies_to_name_value(cookies)
    if "web_session" not in cookie_map and "a1" not in cookie_map:
        return _failure(
            "not_logged_in",
            kw,
            "小红书缺少登录 Cookie（web_session/a1），请先在账号库配置后重试",
        )

    headless = _resolve_headless(headed)
    started = time.perf_counter()
    try:
        from dingda_sidecar.crawlers.vendor.xhs_cli.exceptions import DataFetchError, LoginError

        feeds = await asyncio.to_thread(_search_via_xhs_client_sync, kw, cookie_map, headless)
    except LoginError as error:
        return _failure("not_logged_in", kw, f"小红书需要登录：{error}")
    except DataFetchError as error:
        return _failure("error", kw, f"小红书搜索被风控或无数据：{error}")
    except Exception as error:  # noqa: BLE001
        logger.exception("小红书 XhsClient 搜索异常 keyword=%s", kw)
        return _failure("error", kw, f"小红书搜索失败: {error}")

    offers = [offer for offer in (_feed_to_offer(feed) for feed in feeds) if offer is not None][
        : max(1, max_results)
    ]

    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    logger.info(
        "小红书 xhs-cli 搜索完成 keyword=%s total=%s duration_ms=%s",
        kw,
        len(offers),
        duration_ms,
    )
    return _result(kw, feeds=feeds, offers=offers, final_url=SEARCH_RESULT_URL, engine="xhs-cli")
