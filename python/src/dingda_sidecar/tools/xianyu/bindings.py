"""闲鱼 LangChain 工具 — AI 可见描述与参数。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dingda_sidecar.tools.xianyu.search import search_xianyu


class XianyuSearchArgs(BaseModel):
    keyword: str = Field(description="闲鱼搜索关键词，如品类/成色/型号")
    account_id: str = Field(description="已登录闲鱼账号 ID")
    cookies: list[dict[str, Any]] = Field(description="该账号的浏览器 Cookie 列表")
    max_results: int = Field(default=20, ge=1, le=50, description="最多返回条数")


def _run_xianyu_search(
    keyword: str,
    account_id: str,
    cookies: list[dict[str, Any]],
    max_results: int = 20,
) -> str:
    result = asyncio.run(
        search_xianyu(
            keyword,
            account_id=account_id,
            cookies=cookies,
            max_results=max_results,
        )
    )
    return json.dumps(result, ensure_ascii=False)


def make_xianyu_search_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_run_xianyu_search,
        name="xianyu_search",
        description=(
            "在闲鱼按关键词搜索在售商品，返回 items/offers 列表。"
            "用于核验二手/零售侧真实挂价与供给；需要已登录账号 cookies。"
        ),
        args_schema=XianyuSearchArgs,
    )


__all__ = ["XianyuSearchArgs", "make_xianyu_search_tool"]
