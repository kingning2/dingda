"""选品 Tool：product（单品详情）。

职责：
    契约（Input/Output）与执行（Crawler → BrowserPort）放同一文件。
    供 registry / MCP 注册与调用。

设计说明：
    - 闲鱼详情通常需要 cookie
    - 不 import Playwright / Camoufox

使用示例：
    out = await run_product(ProductInput(platform="xianyu", item_id="1", cookie="..."))
"""

from __future__ import annotations

import logging
import uuid

from pydantic import BaseModel, Field

from src.browser.manager import get_browser_manager
from src.browser.port import LaunchOptions
from src.crawler.core.base import BrowserSessionOptions
from src.crawler.core.types import CrawlContext
from src.crawler.registry import cookies_for, create_crawler
from src.shared.errors import AppError

logger = logging.getLogger("dingda.tools.product")

TOOL_NAME = "product"
TOOL_DESCRIPTION = (
    "按平台与 item_id 拉取单条详情，用于选品时抽样核对（卖家、状态、价格是否与列表一致）。"
    "item_id 必须来自 search 返回，不要手编。"
    "闲鱼详情通常需要已登录账号的 cookie；没有 cookie 时不要硬调，改用 search 列表做判断。"
    "小红书详情可传 xsec_token（若搜索结果里有）。"
    "不支持 ali1688（无独立详情 API）；1688 请用 search 或 compare。"
)
DEFAULT_TIMEOUT_S = 45.0


class ProductInput(BaseModel):
    """商品详情入参。"""

    platform: str = Field(
        description="与 search 相同：xianyu 或 xiaohongshu。不要填 ali1688。"
    )
    item_id: str = Field(description="来自 search 结果的商品/笔记 id")
    cookie: str | None = Field(
        default=None,
        description="账号 cookie。闲鱼详情强烈建议传入；缺失常会失败（account.cookie_required）。",
    )
    xsec_token: str | None = Field(
        default=None,
        description="小红书可选；打开笔记页时用。没有则省略。",
    )
    proxy_url: str | None = Field(default=None, description="可选代理 URL；用户未要求则不要传。")


class ProductItem(BaseModel):
    """单条商品详情。"""

    item_id: str = Field(description="商品或笔记 id")
    title: str = Field(description="标题")
    url: str = Field(description="页面链接")
    price: str | None = Field(default=None, description="价格，可能为空")
    seller_nick: str | None = Field(default=None, description="卖家昵称，可能为空")
    status: str | None = Field(default=None, description="状态文案，可能为空")


class ProductOutput(BaseModel):
    """商品详情出参。"""

    ok: bool = True
    platform: str
    item_id: str
    item: ProductItem | None = None
    error_code: str | None = None
    message: str | None = None


async def run_product(inp: ProductInput) -> ProductOutput:
    """执行商品详情。"""
    task_id = f"mcp-{uuid.uuid4().hex[:12]}"
    logger.info(
        "tool start name=product platform=%s item_id=%s task=%s",
        inp.platform,
        inp.item_id,
        task_id,
    )
    manager = get_browser_manager()
    port = None
    try:
        port = await manager.acquire(LaunchOptions(headless=True))
        options = BrowserSessionOptions(
            proxy_url=inp.proxy_url,
            cookies=cookies_for(inp.platform, inp.cookie),
        )
        crawler = create_crawler(inp.platform, port, options)
        result = await crawler.detail(
            CrawlContext(
                task_id=task_id,
                meta={
                    "cookie": inp.cookie or "",
                    "xsec_token": inp.xsec_token or "",
                },
            ),
            inp.item_id,
        )
        if not result.items:
            return ProductOutput(
                ok=False,
                platform=inp.platform,
                item_id=inp.item_id,
                error_code="crawler.not_found",
                message="未找到商品",
            )
        row = result.items[0]
        raw = row.raw if isinstance(row.raw, dict) else {}
        item = ProductItem(
            item_id=row.item_id,
            title=row.title,
            url=row.url,
            price=row.price,
            seller_nick=str(raw.get("seller_nick") or "") or None,
            status=str(raw.get("status") or "") or None,
        )
        logger.info("tool done name=product item_id=%s", item.item_id)
        return ProductOutput(
            ok=True,
            platform=inp.platform,
            item_id=inp.item_id,
            item=item,
        )
    except AppError as exc:
        logger.warning("tool failed name=product code=%s", exc.code)
        return ProductOutput(
            ok=False,
            platform=inp.platform,
            item_id=inp.item_id,
            error_code=exc.code,
            message=exc.message,
        )
    except Exception as exc:
        logger.exception("tool failed name=product")
        return ProductOutput(
            ok=False,
            platform=inp.platform,
            item_id=inp.item_id,
            error_code="tool.failed",
            message=str(exc),
        )
    finally:
        if port is not None:
            await manager.release(port)
