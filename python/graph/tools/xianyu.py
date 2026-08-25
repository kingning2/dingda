"""闲鱼搜索工具（Graph 侧薄封装）。

把关键词请求转给 ``crawlers.xianyu`` 搜索，返回结构化商品列表。"""

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
    """异步闲鱼关键词搜索。"""
    return await fetch_search(
        keyword,
        account_id=account_id,
        cookies=cookies,
        max_results=max_results,
        headed=headed,
    )
