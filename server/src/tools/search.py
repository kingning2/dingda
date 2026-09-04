"""选品 Tool：search（关键词搜品）。

职责：
    契约（Input/Output）与执行（Crawler → BrowserPort）放同一文件。
    供 registry / MCP 注册与调用。

设计说明：
    - platform：xianyu / xiaohongshu
    - 不 import Playwright / Camoufox

使用示例：
    out = await run_search(SearchInput(platform="xianyu", query="露营椅", limit=20))
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

logger = logging.getLogger("dingda.tools.search")

TOOL_NAME = "search"
TOOL_DESCRIPTION = (
    "按关键词在指定平台搜索商品/笔记列表，用于选品建样本池。"
    "闲鱼（xianyu）：验证某关键词是否近期有量、看挂牌价分布。"
    "小红书（xiaohongshu）：收趋势与可搜关键词，再回闲鱼验证。"
    "返回 item_id / title / url / price；不要用来查 1688。"
    "平台仅支持 xianyu、xiaohongshu。"
)
DEFAULT_TIMEOUT_S = 60.0


class SearchInput(BaseModel):
    """搜品入参。"""

    platform: str = Field(
        description="爬取平台：xianyu=闲鱼（销售侧验证）；xiaohongshu=小红书（趋势/关键词）。不要填 1688/淘宝等。"
    )
    query: str = Field(
        description="搜索关键词。选品时用当下可搜的具体词，避免过大而空的老类目词。"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="返回条数，建议 10～20；先小样本看有没有量再决定是否加深。",
    )
    cookie: str | None = Field(
        default=None,
        description="可选登录 cookie；一般搜索可不传，有账号时再传以提高成功率。",
    )
    proxy_url: str | None = Field(default=None, description="可选代理 URL；用户未要求则不要传。")
    cookie_domain: str | None = Field(
        default=None,
        description="cookie 注入域名；省略则用平台默认，通常不要传。",
    )


class SearchItem(BaseModel):
    """单条搜品结果。"""

    item_id: str = Field(description="商品或笔记 id，后续拉详情用")
    title: str = Field(description="标题")
    url: str = Field(description="页面链接")
    price: str | None = Field(default=None, description="列表价，可能为空")


class SearchOutput(BaseModel):
    """搜品出参。"""

    ok: bool = True
    platform: str
    query: str
    items: list[SearchItem] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None


async def run_search(inp: SearchInput) -> SearchOutput:
    """执行搜品：复用 Browser，只关闭本任务 Page。"""
    task_id = f"mcp-{uuid.uuid4().hex[:12]}"
    logger.info(
        "tool start name=search platform=%s query=%s limit=%s task=%s",
        inp.platform,
        inp.query,
        inp.limit,
        task_id,
    )
    manager = get_browser_manager()
    port = None
    try:
        port = await manager.acquire(LaunchOptions(headless=True))
        options = BrowserSessionOptions(
            proxy_url=inp.proxy_url,
            cookies=cookies_for(inp.platform, inp.cookie),
            cookie_domain=inp.cookie_domain or "",
        )
        crawler = create_crawler(inp.platform, port, options)
        result = await crawler.search(
            CrawlContext(task_id=task_id, meta={"limit": inp.limit}),
            inp.query,
        )
        rows = [
            SearchItem(
                item_id=item.item_id,
                title=item.title,
                url=item.url,
                price=item.price,
            )
            for item in result.items
        ]
        logger.info("tool done name=search count=%s", len(rows))
        return SearchOutput(
            ok=True,
            platform=inp.platform,
            query=inp.query,
            items=rows,
        )
    except AppError as exc:
        logger.warning("tool failed name=search code=%s", exc.code)
        return SearchOutput(
            ok=False,
            platform=inp.platform,
            query=inp.query,
            error_code=exc.code,
            message=exc.message,
        )
    except Exception as exc:
        logger.exception("tool failed name=search")
        return SearchOutput(
            ok=False,
            platform=inp.platform,
            query=inp.query,
            error_code="tool.failed",
            message=str(exc),
        )
    finally:
        if port is not None:
            await manager.release(port)
