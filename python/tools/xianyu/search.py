"""闲鱼搜索实现 — 转调 crawlers.xianyu。"""

from __future__ import annotations

from typing import Any

from crawlers.xianyu import fetch_search


async def search_xianyu(
    keyword: str,
    *,
    account_id: str,
    cookies: list[dict[str, Any]],
    max_results: int = 20,
    headed: bool | None = None,
) -> dict[str, Any]:
    return await fetch_search(
        keyword,
        account_id=account_id,
        cookies=cookies,
        max_results=max_results,
        headed=headed,
    )
