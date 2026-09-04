"""平台采集层：搜品 / 详情 / 解析；经 BrowserPort 开页，不直连 Playwright。"""

from __future__ import annotations

from src.crawler.core.base import BrowserCrawler, BrowserSessionOptions
from src.crawler.core.types import CrawlContext, CrawlItem, CrawlResult
from src.crawler.registry import create_crawler, list_platforms
from src.crawler.service import CrawlerService

__all__ = [
    "BrowserCrawler",
    "BrowserSessionOptions",
    "CrawlContext",
    "CrawlItem",
    "CrawlResult",
    "CrawlerService",
    "create_crawler",
    "list_platforms",
]
