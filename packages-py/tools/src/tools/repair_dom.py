"""编排 Tool：repair_dom（父调度 DOM 修复）。

职责：
    worker 上报 ``crawler.needs_repair`` 后，父强制 ``DINGDA_REPAIR_OWNER=crawler``
    再跑 ``product``，走 crawler 内联 ``repair_detail_dom``；成功后把 worker 迁到 resuming。

设计说明：
    - 不另开一套修页逻辑，复用详情链路里的指纹 / AI 修复
    - 修完父再 ``child_resume``

使用示例：
    out = await run_repair_dom(RepairDomInput(platform="xianyu", item_id="123"))
"""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("dingda.tools.repair_dom")

TOOL_NAME = "repair_dom"
TOOL_DESCRIPTION = (
    "父编排器调度 DOM 自动修复。"
    "worker 返回 needs_repair 后调用；成功后再 child_resume。"
)
DEFAULT_TIMEOUT_S = 900.0


class RepairDomInput(BaseModel):
    """修复入参。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu")
    item_id: str = Field(description="商品或笔记 id")
    url: str | None = Field(default=None, description="详情 URL（可选，仅记录）")
    worker_run_id: str | None = Field(
        default=None,
        description="对应 worker 的 run_id；有则把 phase 迁到 repairing/resuming",
    )


class RepairDomOutput(BaseModel):
    """修复出参。"""

    ok: bool = True
    platform: str = ""
    item_id: str = ""
    error_code: str | None = None
    message: str | None = None
    patch_source: str | None = None
    repair: dict[str, Any] | None = None


async def run_repair_dom(inp: RepairDomInput) -> RepairDomOutput:
    """强制内联修复并再抽一次详情。"""
    from cli.lifecycle import AgentPhase
    from cli.registry import get_run_store
    from tools.product import ProductInput, run_product

    platform = inp.platform.strip().lower()
    item_id = inp.item_id.strip()
    worker_run = (inp.worker_run_id or "").strip() or None
    store = get_run_store()
    repair_meta = {"platform": platform, "item_id": item_id, "url": inp.url or ""}

    if worker_run and store.get(worker_run):
        store.transition(worker_run, AgentPhase.REPAIRING, step="repair_dom")

    logger.info("tool start name=repair_dom platform=%s item_id=%s", platform, item_id)
    previous = os.environ.get("DINGDA_REPAIR_OWNER")
    os.environ["DINGDA_REPAIR_OWNER"] = "crawler"
    try:
        out = await run_product(
            ProductInput(platform=platform, item_id=item_id),
            allow_login_recovery=False,
        )
        if out.ok and out.item is not None:
            if worker_run and store.get(worker_run):
                store.transition(worker_run, AgentPhase.RESUMING, step="repair_ok")
            logger.info("tool done name=repair_dom ok")
            return RepairDomOutput(
                ok=True,
                platform=platform,
                item_id=item_id,
                message="DOM 修复成功，详情可抽取",
                patch_source="inline",
                repair=repair_meta,
            )

        code = out.error_code or "crawler.dom_repair_failed"
        if worker_run and store.get(worker_run):
            store.transition(
                worker_run,
                AgentPhase.FAILED,
                step="repair_fail",
                error_code=code,
            )
        logger.warning("tool failed name=repair_dom code=%s", code)
        return RepairDomOutput(
            ok=False,
            platform=platform,
            item_id=item_id,
            error_code=code,
            message=out.message or "DOM 修复失败",
            repair=repair_meta,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("tool failed name=repair_dom")
        if worker_run and store.get(worker_run):
            store.transition(
                worker_run,
                AgentPhase.FAILED,
                step="repair_exception",
                error_code="tool.failed",
            )
        return RepairDomOutput(
            ok=False,
            platform=platform,
            item_id=item_id,
            error_code="tool.failed",
            message=str(exc)[:300],
            repair=repair_meta,
        )
    finally:
        if previous is None:
            os.environ.pop("DINGDA_REPAIR_OWNER", None)
        else:
            os.environ["DINGDA_REPAIR_OWNER"] = previous
