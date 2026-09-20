"""修复工具：把详情页当前的 DOM 结构摆给模型看，收下它给的选择器。

职责：
    给修复子 agent 两个动作 —— ``inspect_dom``（打开详情页、导出精简 DOM 树、连同
    当前选择器与必填字段一起返回）与 ``submit_patch``（交出候选选择器）。

设计说明：
    - **本工具不写盘**：写盘（热更新 ``extract.json``）在 ``tools/validate.py``，
      验证通过才落。修复与验证分开，是为了让「改坏了」止步于候选，不污染线上选择器。
    - 真正被替换的只是 ``detail_dom`` 这一个 section 的选择器，``signals`` 等其它
      section 不动 —— 那是平台抓取判断「是不是风控 / 登录墙」的依据，改不得。
    - 导出的是**精简树**（``dump_dom_tree``，默认 6 层）：把整页 HTML 给模型既超
      预算又淹没结构，只留能定位字段的那部分。
"""

from __future__ import annotations

import logging
from typing import Any

from crawler.extraction.repair.dump import dump_dom_tree
from crawler.extraction.repair.gates import looks_risk_text
from crawler.sources.xianyu import extractor as xianyu_ex
from crawler.sources.xianyu.repair_adapter import (
    XianyuDetailRepairAdapter,
    XianyuSearchRepairAdapter,
)
from crawler.sources.xiaohongshu import extractor as xhs_ex
from crawler.sources.xiaohongshu.repair_adapter import (
    XiaohongshuDetailRepairAdapter,
    XiaohongshuSearchRepairAdapter,
)
from pydantic import BaseModel, Field

from agent.context import RunContext
from agent.loop import ToolSpec
from agent.session import crawl_session
from agent.steps import platform_label

logger = logging.getLogger("dingda.agent.tool.repair")

_ADAPTERS: dict[tuple[str, str], type] = {
    ("xianyu", "detail_dom"): XianyuDetailRepairAdapter,
    ("xianyu", "dom"): XianyuSearchRepairAdapter,
    ("xiaohongshu", "detail_dom"): XiaohongshuDetailRepairAdapter,
    ("xiaohongshu", "dom"): XiaohongshuSearchRepairAdapter,
}


async def inspect_dom(
    ctx: RunContext,
    platform: str,
    item_id: str,
    section: str = "detail_dom",
    query: str = "",
    xsec_token: str | None = None,
) -> dict[str, Any]:
    """打开目标页面（搜索页或详情页），导出当前 DOM 结构给模型看。"""
    plat = (platform or "").strip().lower()
    sec = (section or "detail_dom").strip()
    adapter_cls = _ADAPTERS.get((plat, sec))
    if adapter_cls is None:
        return _fail(plat, "agent.invalid_input", f"不支持的平台或 section：{plat}/{sec}")
    if not (item_id or "").strip():
        return _fail(plat, "agent.invalid_input", "item_id 不能为空")

    adapter = adapter_cls()
    url = _page_url(plat, sec, item_id, query, xsec_token)
    try:
        async with crawl_session(plat, ctx=ctx, cookie=ctx.cookie_for(plat)) as session:
            page = await session.crawler.open_page(session.ctx())
            try:
                await page.goto(url)
                tree = await dump_dom_tree(page, roots=adapter.dump_roots())
            finally:
                await session.crawler.close_page(page)
    except Exception as exc:  # noqa: BLE001 — 工具层不抛，主编排靠 error_code 分流
        logger.exception("DOM 导出失败 platform=%s item=%s", plat, item_id)
        return _fail(plat, "crawler.failed", str(exc))

    preview = str(tree.get("preview") or "")
    if looks_risk_text(preview):
        logger.warning("DOM 导出撞到风控 platform=%s item=%s", plat, item_id)
        return _fail(plat, "channel.risk", "详情页处于风控页，先过风控再修")

    logger.info(
        "DOM 导出完成 platform=%s item=%s fields=%s",
        plat,
        item_id,
        adapter.required_fields(),
    )
    return {
        "ok": True,
        "platform": plat,
        "item_id": item_id,
        "section": adapter.section_name,
        "required_fields": adapter.required_fields(),
        "current_selectors": adapter.current_selectors(),
        "trees": tree.get("trees") or [],
        "preview": preview[:240],
    }


async def submit_patch(
    ctx: RunContext,
    platform: str,
    item_id: str,
    selectors: dict[str, Any],
    section: str = "detail_dom",
) -> dict[str, Any]:
    """交出候选选择器；**不落盘**，等验证通过再热更新。"""
    plat = (platform or "").strip().lower()
    sec = (section or "detail_dom").strip()
    adapter_cls = _ADAPTERS.get((plat, sec))
    if adapter_cls is None:
        return _fail(plat, "agent.invalid_input", f"不支持的平台或 section：{plat}/{sec}")
    if not selectors:
        return _fail(plat, "agent.invalid_input", "selectors 不能为空")

    missing = [f for f in adapter_cls().required_fields() if f not in selectors]
    if missing:
        return _fail(plat, "agent.invalid_input", f"缺少必填字段的选择器：{'、'.join(missing)}")

    logger.info("收到候选选择器 platform=%s item=%s keys=%s", plat, item_id, sorted(selectors))
    return {
        "ok": True,
        "platform": plat,
        "item_id": (item_id or "").strip(),
        "section": adapter_cls().section_name,
        "selectors": selectors,
    }


def _detail_url(platform: str, item_id: str, xsec_token: str | None) -> str:
    """按平台拼详情页 URL；小红书要带搜索下发的 ``xsec_token``。"""
    if platform == "xianyu":
        return f"{xianyu_ex.ITEM_URL}?id={item_id}"
    token = (xsec_token or "").strip()
    suffix = f"?xsec_token={token}" if token else ""
    return f"{xhs_ex.NOTE_URL}/{item_id}{suffix}"


def _page_url(
    platform: str,
    section: str,
    item_id: str,
    query: str,
    xsec_token: str | None,
) -> str:
    """按平台 + section 拼目标页面 URL；搜索页修复时用 query 导航。"""
    if section == "dom":
        if platform == "xianyu":
            q = (query or "商品").strip()
            return f"{xianyu_ex.SEARCH_URL}?q={q}"
        search_url = str(xhs_ex._URLS.get("search") or "https://www.xiaohongshu.com/search_result")
        q = (query or "商品").strip()
        return f"{search_url}?keyword={q}"
    return _detail_url(platform, item_id, xsec_token)


def _fail(platform: str, code: str, message: str) -> dict[str, Any]:
    """失败出参。"""
    return {
        "ok": False,
        "platform": platform or "unknown",
        "error_code": code,
        "message": f"{platform_label(platform)}：{message}",
        "selectors": {},
    }


class InspectInput(BaseModel):
    """导出 DOM 的入参。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu")
    item_id: str = Field(description="商品或笔记 id")
    section: str = Field(default="detail_dom", description="修复目标：dom（搜索/列表）或 detail_dom（详情）")
    query: str = Field(default="", description="搜索页修复时的关键词；section=dom 时必传")
    xsec_token: str | None = Field(default=None, description="小红书详情偶发需要")


class SubmitInput(BaseModel):
    """提交候选选择器的入参。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu")
    item_id: str = Field(description="商品或笔记 id")
    selectors: dict[str, Any] = Field(
        description="候选选择器：键是字段名（见 inspect_dom 的 required_fields），值是 CSS 选择器",
    )
    section: str = Field(default="detail_dom", description="修复目标：dom（搜索/列表）或 detail_dom（详情）")


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="inspect_dom",
        label="检查 DOM · {platform}",
        description=(
            "打开目标页面（搜索页 / 详情页，由 section 决定），导出当前 DOM 结构与现有选择器。"
            "section=dom 时必须传 query（搜索关键词），item_id 可传空串；"
            "section=detail_dom 时传 item_id。先看清楚元素在哪，再提候选。"
        ),
        args=InspectInput,
        fn=inspect_dom,
        browser=True,
    ),
    ToolSpec(
        name="submit_patch",
        label="提交选择器 · {platform}",
        description=(
            "交出候选选择器（只改 section 指定的小节，必填字段一个都不能少）。"
            "**这是本任务的最后一步**：提完就结束，由主编排转交验证。"
        ),
        args=SubmitInput,
        fn=submit_patch,
    ),
)
