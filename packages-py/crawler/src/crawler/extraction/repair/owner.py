"""DOM 修复归属策略。

职责：
    详情抽取失败时决定「crawler 内联修」还是「上抛给父编排器」。
    平台 crawler 只调 ``get_repair_owner().on_dom_extract_failed``，不散落 if env。

设计说明：
    - ``DINGDA_REPAIR_OWNER=parent``（worker 默认）→ escalate ``crawler.needs_repair``
    - ``DINGDA_REPAIR_OWNER=crawler``（e2e / 旧路径）→ inline ``repair_detail_dom``

使用示例：
    decision = get_repair_owner().on_dom_extract_failed(ctx)
    if decision.action == "escalate":
        raise decision.error
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

from contracts.browser_port import Page
from core.errors import AppError
from crawler.extraction.repair.types import PlatformRepairAdapter, RepairResult

logger = logging.getLogger("dingda.crawler.repair.owner")


@dataclass(frozen=True)
class RepairContext:
    """详情 DOM 失败现场。"""

    page: Page
    adapter: PlatformRepairAdapter
    item_id: str
    url: str = ""
    platform: str = ""


@dataclass(frozen=True)
class RepairDecision:
    """归属决策：inline 带 result；escalate 带 AppError。"""

    action: Literal["inline", "escalate"]
    result: RepairResult | None = None
    error: AppError | None = None


class RepairOwner(ABC):
    """修复归属插座。"""

    @abstractmethod
    async def on_dom_extract_failed(self, ctx: RepairContext) -> RepairDecision:
        """抽取失败后的下一步。"""


class EscalateToParent(RepairOwner):
    """上抛给父编排器。"""

    async def on_dom_extract_failed(self, ctx: RepairContext) -> RepairDecision:
        """构造 needs_repair，不跑 AI 修复。"""
        platform = (ctx.platform or ctx.adapter.platform or "").strip()
        details = {
            "platform": platform,
            "item_id": ctx.item_id,
            "url": ctx.url or "",
        }
        logger.info(
            "repair escalate platform=%s item_id=%s",
            platform,
            ctx.item_id,
        )
        return RepairDecision(
            action="escalate",
            error=AppError(
                "crawler.needs_repair",
                (
                    f"详情 DOM 失效，需父进程 repair_dom："
                    f"platform={platform} item_id={ctx.item_id}"
                ),
                status_code=502,
                details=details,
            ),
        )


class InlineCrawlerRepair(RepairOwner):
    """crawler 内联调用 repair_detail_dom。"""

    async def on_dom_extract_failed(self, ctx: RepairContext) -> RepairDecision:
        """跑现有编排并返回结果。"""
        from crawler.extraction.repair.orchestrator import repair_detail_dom

        logger.info(
            "repair inline platform=%s item_id=%s",
            ctx.adapter.platform,
            ctx.item_id,
        )
        result = await repair_detail_dom(ctx.page, ctx.adapter, item_id=ctx.item_id)
        return RepairDecision(action="inline", result=result)


def get_repair_owner() -> RepairOwner:
    """读 ``DINGDA_REPAIR_OWNER``；默认 parent（上抛）。"""
    value = (os.getenv("DINGDA_REPAIR_OWNER") or "parent").strip().lower()
    if value in {"crawler", "inline"}:
        return InlineCrawlerRepair()
    return EscalateToParent()
