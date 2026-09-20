"""验证工具：候选选择器好不好使，好使才热更新。

职责：
    给验证子 agent 两个动作 —— ``try_selectors``（用候选选择器真抽一次，判定抽到了
    没有 / 是不是风控 / 是不是登录墙）与 ``commit_selectors``（写回 ``extract.json``
    并热加载）。

设计说明：
    - **先试后写**：候选选择器可能把页面抽空或抽错字段，落盘前必须真跑一次。
      ``commit_selectors`` 只在 ``try_selectors`` 判定通过后由模型调用。
    - 判定口径复用平台 adapter 的 ``payload_ok`` / ``is_risk_payload`` /
      ``is_auth_payload``：什么是「抽到了」由平台自己说，agent 不另立标准。
    - 热更新走 ``write_extract_section``（写盘 + 重载），不重启进程、不影响在跑的
      其它会话；下一次抓取就用上新选择器。
"""

from __future__ import annotations

import logging
from typing import Any

from crawler.extraction.config import write_extract_section
from pydantic import BaseModel, Field

from agent.context import RunContext
from agent.loop import ToolSpec
from agent.session import crawl_session
from agent.steps import platform_label
from agent.tools.repair import _ADAPTERS, _detail_url, _page_url

logger = logging.getLogger("dingda.agent.tool.validate")


async def try_selectors(
    ctx: RunContext,
    platform: str,
    item_id: str,
    selectors: dict[str, Any],
    section: str = "detail_dom",
    query: str = "",
    xsec_token: str | None = None,
) -> dict[str, Any]:
    """用候选选择器真抽一次详情，报抽到了没有。"""
    plat = (platform or "").strip().lower()
    sec = (section or "detail_dom").strip()
    adapter_cls = _ADAPTERS.get((plat, sec))
    if adapter_cls is None:
        return _fail(plat, "agent.invalid_input", f"不支持的平台或 section：{plat}/{sec}")
    if not selectors:
        return _fail(plat, "agent.invalid_input", "selectors 不能为空")

    adapter = adapter_cls()
    url = _page_url(plat, sec, item_id, query, xsec_token)
    try:
        async with crawl_session(plat, ctx=ctx, cookie=ctx.cookie_for(plat)) as session:
            page = await session.crawler.open_page(session.ctx())
            try:
                await page.goto(url)
                payload = await adapter.evaluate_extract(page, selectors, item_id=item_id)
            finally:
                await session.crawler.close_page(page)
    except Exception as exc:  # noqa: BLE001 — 选择器非法会让 evaluate 抛，按「这次没抽到」处理
        logger.warning("选择器验证异常 platform=%s detail=%s", plat, exc)
        return _fail(plat, "crawler.selector_invalid", f"选择器跑不通：{exc}"[:200])

    if adapter.is_risk_payload(payload):
        logger.warning("验证撞到风控 platform=%s item=%s", plat, item_id)
        return _fail(plat, "channel.risk", "详情页处于风控页，先过风控再验证")
    if adapter.is_auth_payload(payload):
        logger.warning("验证撞到登录墙 platform=%s item=%s", plat, item_id)
        return _fail(plat, "account.session_expired", "登录已失效，需要重新扫码")

    valid = adapter.payload_ok(payload)
    logger.info("选择器验证完成 platform=%s item=%s valid=%s", plat, item_id, valid)
    if not valid:
        return _fail(plat, "crawler.validate_failed", "用这组选择器没抽到有效字段", payload=payload)
    return {
        "ok": True,
        "platform": plat,
        "item_id": (item_id or "").strip(),
        "valid": True,
        "payload": payload,
        "message": "验证通过，可以热更新",
    }


async def commit_selectors(
    ctx: RunContext,
    platform: str,
    selectors: dict[str, Any],
    section: str = "detail_dom",
) -> dict[str, Any]:
    """把验证通过的选择器写回 ``extract.json`` 并热加载。"""
    plat = (platform or "").strip().lower()
    sec = (section or "detail_dom").strip()
    adapter_cls = _ADAPTERS.get((plat, sec))
    if adapter_cls is None:
        return _fail(plat, "agent.invalid_input", f"不支持的平台或 section：{plat}/{sec}")
    if not selectors:
        return _fail(plat, "agent.invalid_input", "selectors 不能为空")

    adapter = adapter_cls()
    try:
        write_extract_section(adapter.extract_beside, adapter.section_name, selectors)
    except Exception as exc:  # noqa: BLE001 — 写盘失败要明确报，别静默当成成功
        logger.exception("热更新失败 platform=%s", plat)
        return _fail(plat, "crawler.persist_failed", str(exc))

    logger.info("选择器已热更新 platform=%s section=%s", plat, adapter.section_name)
    return {
        "ok": True,
        "platform": plat,
        "section": adapter.section_name,
        "message": f"{platform_label(plat)}选择器已热更新，后续抓取即用新配置",
    }


def _fail(
    platform: str,
    code: str,
    message: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """失败出参；带上 payload 方便主编排查「抽到了什么、错在哪」。"""
    out: dict[str, Any] = {
        "ok": False,
        "platform": platform or "unknown",
        "valid": False,
        "error_code": code,
        "message": f"{platform_label(platform)}：{message}",
    }
    if payload:
        out["payload"] = payload
    return out


class TryInput(BaseModel):
    """试跑候选选择器的入参。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu")
    item_id: str = Field(description="商品或笔记 id")
    selectors: dict[str, Any] = Field(description="待验证的候选选择器")
    section: str = Field(default="detail_dom", description="修复目标：dom（搜索/列表）或 detail_dom（详情）")
    query: str = Field(default="", description="搜索页修复时的关键词；section=dom 时必传")
    xsec_token: str | None = Field(default=None, description="小红书详情偶发需要")


class CommitInput(BaseModel):
    """热更新选择器的入参。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu")
    selectors: dict[str, Any] = Field(description="**已验证通过**的候选选择器")
    section: str = Field(default="detail_dom", description="修复目标：dom（搜索/列表）或 detail_dom（详情）")


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="try_selectors",
        label="验证选择器 · {platform}",
        description=(
            "用候选选择器真抽一次（section 决定搜索页或详情页），报抽到了没有。"
            "抽到有效字段才算通过；风控与登录墙会如实报出来。"
        ),
        args=TryInput,
        fn=try_selectors,
        browser=True,
    ),
    ToolSpec(
        name="commit_selectors",
        label="热更新选择器 · {platform}",
        description=(
            "把**已通过 try_selectors** 的选择器写回配置并热加载。"
            "没验证过就写会把平台抓崩 —— 必须先试后写。"
        ),
        args=CommitInput,
        fn=commit_selectors,
    ),
)
