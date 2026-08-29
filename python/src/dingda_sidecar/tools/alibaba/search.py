"""1688 搜索实现 — 转调 crawlers.alibaba。"""

from __future__ import annotations

from typing import Any

from dingda_sidecar.crawlers.alibaba import fetch_search


async def search_alibaba(
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
