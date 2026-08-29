"""1688 LangChain 工具 — AI 可见描述与参数。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dingda_sidecar.tools.alibaba.search import search_alibaba


class AlibabaSearchArgs(BaseModel):
    keyword: str = Field(description="1688 搜索关键词，如品类/型号/规格")
    account_id: str = Field(description="已登录 1688 账号 ID")
    cookies: list[dict[str, Any]] = Field(description="该账号的浏览器 Cookie 列表")
    max_results: int = Field(default=20, ge=1, le=50, description="最多返回条数")


def _run_alibaba_search(
    keyword: str,
    account_id: str,
    cookies: list[dict[str, Any]],
    max_results: int = 20,
) -> str:
    result = asyncio.run(
        search_alibaba(
            keyword,
            account_id=account_id,
            cookies=cookies,
            max_results=max_results,
        )
    )
    return json.dumps(result, ensure_ascii=False)


def make_alibaba_search_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=_run_alibaba_search,
        name="alibaba_search",
        description=(
            "在 1688 按关键词搜索货源/报价，返回 offers 列表。"
            "用于核验网上说的货源是否真实存在；需要已登录账号 cookies。"
        ),
        args_schema=AlibabaSearchArgs,
    )


__all__ = ["AlibabaSearchArgs", "make_alibaba_search_tool"]
