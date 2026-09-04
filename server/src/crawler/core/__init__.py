"""爬虫核心包：BrowserCrawler 插座与共享类型。"""

from __future__ import annotations

from src.crawler.core.base import BrowserCrawler, BrowserSessionOptions
from src.crawler.core.types import CrawlContext, CrawlItem, CrawlResult

__all__ = [
    "BrowserCrawler",
    "BrowserSessionOptions",
    "CrawlContext",
    "CrawlItem",
    "CrawlResult",
]
