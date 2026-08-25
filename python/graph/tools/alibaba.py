"""1688 搜索工具（Graph 侧薄封装）。

把关键词请求转给 ``crawlers.alibaba`` 搜索，返回结构化 offer 列表。"""

from __future__ import annotations

from typing import Any

from crawlers.alibaba import fetch_search


async def search_alibaba(
    keyword: str,
    *,
    account_id: str,
    cookies: list[dict[str, Any]],
    max_results: int = 20,
    headed: bool | None = None,
) -> dict[str, Any]:
    """异步 1688 关键词搜索。"""
    return await fetch_search(
        keyword,
        account_id=account_id,
        cookies=cookies,
        max_results=max_results,
        headed=headed,
    )
