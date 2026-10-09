"""监控概览端点。

职责：
    概览统计：多少还在卖、多少卖掉了、多少降价了。
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from api.routes.watch._dto import WatchSummaryResponse
from domains.watch.service import summarize

router = APIRouter()


@router.get("/summary", response_model=WatchSummaryResponse)
def watch_summary() -> WatchSummaryResponse:
    """概览：多少还在卖、多少卖掉了、多少降价了。"""
    return WatchSummaryResponse(**asdict(summarize()))
