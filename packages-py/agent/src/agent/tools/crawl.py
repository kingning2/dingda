"""爬虫工具：搜一批商品、拉一条详情。

职责：
    给爬虫子 agent 两个动作 —— ``search_items``（按关键词出列表壳）与
    ``fetch_detail``（按 item_id 拉一条完整事实）。

设计说明：
    - **只出列表壳，不顺手拉详情**：逐条详情很慢，要不要看某一条由主编排决定。
    - 平台路由只有两种：浏览器平台（闲鱼 / 小红书）走 ``crawl_session``，
      1688 走官方找货 API（不开浏览器，也没有详情接口）。
    - **风控优先自动过**：撞到 ``channel.risk`` 先等几秒换个新会话再来一次；
      还过不了才回报 ``channel.risk``，让主编排决定要不要开有头窗口。
    - **登录失效不在这里自救**：原样回报 ``account.session_expired``，由主编排查扫码。
      工具层擅自插扫码会让前端出现「抓取中突然冒出二维码」的错乱顺序。
    - 失败统一 ``ok=False`` + ``error_code``，不抛异常：主编排靠 error_code 分流。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from crawler.core.types import CrawlContext
from crawler.registry import create_api_crawler
from pydantic import BaseModel, Field

from agent.context import RunContext
from agent.items import item_from_row
from agent.loop import ToolSpec
from agent.session import crawl_session
from agent.steps import platform_label

logger = logging.getLogger("dingda.agent.tool.crawl")

_BROWSER_PLATFORMS = frozenset({"xianyu", "xiaohongshu"})
_API_PLATFORMS = frozenset({"ali1688"})
_SUPPORTED = _BROWSER_PLATFORMS | _API_PLATFORMS

_RISK_WAIT_S = 8
_RISK_TRIES = 2


class SearchInput(BaseModel):
    """搜索入参。"""

    platform: str = Field(description="平台：xianyu=闲鱼；xiaohongshu=小红书；ali1688=1688")
    query: str = Field(description="搜索关键词，不要手编商品 id")
    limit: int = Field(
        default=30,
        ge=1,
        le=100,
        description="返回条数上限。不够就换词再搜，不要一次要太多。",
    )


class DetailInput(BaseModel):
    """详情入参。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu（1688 没有详情接口）")
    item_id: str = Field(description="来自搜索结果的 item_id，不要手编")
    xsec_token: str | None = Field(
        default=None,
        description="小红书搜索下发的 token，拉详情必须带回，否则平台返 300031",
    )




async def search_items(
    ctx: RunContext,
    platform: str,
    query: str,
    limit: int = 30,
) -> dict[str, Any]:
    """按关键词搜一批商品 / 笔记；只出列表壳，不含描述与留言。"""
    plat = (platform or "").strip().lower()
    unsupported = _unsupported(plat, query)
    if unsupported is not None:
        return unsupported

    if plat in _API_PLATFORMS:
        return await _guarded(ctx, plat, _api_search(ctx, plat, query, limit))

    async def attempt(cookie: str | None) -> Any:
        """开一个新会话搜一次 —— 重试必须换新会话，cookie 是建 Context 时注入的。"""
        async with crawl_session(plat, ctx=ctx, cookie=cookie, extra_meta={"limit": limit}) as session:
            return await session.crawler.search(session.ctx(), query)

    return await _guarded(ctx, plat, _retry_on_risk(ctx, plat, attempt), query=query)


async def fetch_detail(
    ctx: RunContext,
    platform: str,
    item_id: str,
    xsec_token: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """按 item_id 拉一条商品 / 笔记的完整事实。"""
    plat = (platform or "").strip().lower()
    if plat not in _SUPPORTED:
        return _fail(plat, "agent.invalid_input", f"不支持的平台 {platform or '(空)'}")
    if plat in _API_PLATFORMS:
        return _fail(plat, "agent.invalid_input", "1688 走官方找货接口，没有独立详情")
    if not (item_id or "").strip():
        return _fail(plat, "agent.invalid_input", "item_id 不能为空")

    meta: dict[str, Any] = {}
    if plat == "xiaohongshu":
        # 搜索下发的 token 必须原样带回，否则平台返 300031
        meta["xsec_token"] = (xsec_token or "").strip()
    if url:
        meta["url"] = url.strip()

    async def attempt(cookie: str | None) -> Any:
        async with crawl_session(plat, ctx=ctx, cookie=cookie, extra_meta=meta) as session:
            return await session.crawler.detail(session.ctx(), item_id)

    return await _guarded(ctx, plat, _retry_on_risk(ctx, plat, attempt), item_id=item_id)


async def _api_search(ctx: RunContext, platform: str, query: str, limit: int) -> dict[str, Any]:
    """1688 官方找货：不开浏览器，所以不占浏览器池、也没有直播帧。"""
    crawler = create_api_crawler(platform)
    result = await crawler.search(
        CrawlContext(task_id=ctx.task_id, meta={"limit": limit}),
        query,
    )
    return _ok(platform, rows=list(result.items), query=query)


async def _retry_on_risk(ctx: RunContext, platform: str, attempt: Any) -> dict[str, Any]:
    """跑一次抓取；撞风控就等一会儿换个会话再来一次，仍风控则原样抛出。"""
    last: Exception | None = None
    for index in range(_RISK_TRIES):
        try:
            result = await attempt(ctx.cookie_for(platform))
        except Exception as exc:  # noqa: BLE001 — 风控码可能包在 AppError 里
            from core.errors import AppError

            code = getattr(exc, "code", "") if isinstance(exc, AppError) else ""
            last = exc
            if code == "channel.risk" and index + 1 < _RISK_TRIES:
                logger.info("撞到风控，等待 %ss 后换会话重试 platform=%s", _RISK_WAIT_S, platform)
                await asyncio.sleep(_RISK_WAIT_S)
                continue
            raise
        return _ok(platform, rows=list(getattr(result, "items", ()) or ()))
    if last is not None:
        raise last
    return _ok(platform, rows=[])


async def _guarded(
    ctx: RunContext,
    platform: str,
    coro: Any,
    **extra: Any,
) -> dict[str, Any]:
    """跑一段抓取并把异常收成失败出参：主编排靠 ``error_code`` 分流，不接异常。"""
    from core.errors import AppError

    try:
        result = await coro
    except AppError as exc:
        logger.warning("抓取失败 platform=%s code=%s", platform, exc.code)
        result = _fail(platform, exc.code, exc.message)
        if exc.details:
            result["details"] = exc.details
        return result
    except Exception as exc:  # noqa: BLE001 — 工具的意外也不该炸穿编排循环
        logger.exception("抓取异常 platform=%s", platform)
        return _fail(platform, "crawler.failed", str(exc))
    if isinstance(result, dict):
        result.update(extra)
        return result
    return result


def _ok(platform: str, *, rows: list[Any], **extra: Any) -> dict[str, Any]:
    """crawler 的行 → 成功出参。"""
    items = [item_from_row(row, platform=platform).model_dump() for row in rows]
    logger.info("抓取完成 platform=%s count=%s", platform, len(items))
    return {"ok": True, "platform": platform, "items": items, **extra}


def _unsupported(plat: str, query: str) -> dict[str, Any] | None:
    """平台与关键词的入参校验；合法返回 None。"""
    if plat not in _SUPPORTED:
        return _fail(plat, "agent.invalid_input", f"不支持的平台 {plat or '(空)'}")
    if not (query or "").strip():
        return _fail(plat, "agent.invalid_input", "搜索关键词不能为空")
    return None


def _fail(platform: str, code: str, message: str) -> dict[str, Any]:
    """失败出参：形状与成功时对齐（都带 platform），只多 error_code / message。"""
    label = platform_label(platform)
    return {
        "ok": False,
        "platform": platform or "unknown",
        "items": [],
        "error_code": code,
        "message": f"{label}：{message}",
    }


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="search_items",
        label="搜索商品 · {platform}",
        description=(
            "按关键词搜一批商品 / 笔记，结果只是列表壳（id / 标题 / 链接 / 价格 / 卖家），"
            "**不含描述与留言**。要看清某一条，拿 item_id 再调 fetch_detail。"
            "关键词要换着搜：同一批词永远是同一批货。"
        ),
        args=SearchInput,
        fn=search_items,
        browser=True,
    ),
    ToolSpec(
        name="fetch_detail",
        label="查看详情 · {platform}",
        description=(
            "按 item_id 拉一条商品 / 笔记的完整事实：描述、留言、卖家、地区、图文正文。"
            "item_id 必须来自 search_items 的结果；小红书还要带回 xsec_token。"
        ),
        args=DetailInput,
        fn=fetch_detail,
        browser=True,
    ),
)
