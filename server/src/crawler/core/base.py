"""爬虫浏览器会话基类：统一 context、代理、指纹，供各平台 Source 继承。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping, Sequence

from src.browser.context import ContextOptions
from src.browser.port import BrowserPort, Cookie, Page
from src.crawler.core.types import CrawlContext, CrawlResult
from src.shared.errors import AppError

logger = logging.getLogger("dingda.crawler.base")


@dataclass(frozen=True)
class BrowserSessionOptions:
    """一次抓取的浏览器策略（由调用方传入，基类落到 Browser ContextOptions）。"""

    proxy_url: str | None = None
    fingerprint_profile: str | None = None
    cookies: Sequence[Cookie] | Mapping[str, str] | None = None
    # dict cookies 注入时必填；平台 Source 构造时传入（如 .goofish.com）
    cookie_domain: str = ""


class BrowserCrawler(ABC):
    """爬虫插座：打开/关闭带代理与指纹的 page；子类只实现平台抓取。"""

    platform: str

    def __init__(
        self,
        browser: BrowserPort,
        options: BrowserSessionOptions | None = None,
    ) -> None:
        self._browser = browser
        self._options = options or BrowserSessionOptions()

    @classmethod
    def cookies_from_header(cls, cookie: str | None) -> Sequence[Cookie] | None:
        """把 cookie 头转成本平台 Browser Cookie；默认不注入。"""
        return None

    def context_options(self) -> ContextOptions:
        """把爬虫会话策略收成 Browser ContextOptions。"""
        return ContextOptions(
            proxy_url=self._options.proxy_url,
            fingerprint_profile=self._options.fingerprint_profile,
            cookies=self._options.cookies,
            default_cookie_domain=self._options.cookie_domain,
        )

    async def open_page(self, ctx: CrawlContext) -> Page:
        """按代理/指纹/Cookie 策略打开一页，给平台抓取用。"""
        opts = self.context_options()
        logger.info(
            "打开抓取页 platform=%s proxy=%s fingerprint=%s task=%s",
            self.platform,
            bool(opts.proxy_url),
            opts.fingerprint_profile,
            ctx.task_id,
        )
        page = await self._browser.open(
            proxy=opts.proxy_url,
            fingerprint=opts.fingerprint_profile,
            cookies=opts.cookies,
            default_domain=opts.default_cookie_domain,
        )
        return page

    async def close_page(self, page: Page) -> None:
        """关闭本轮抓取页。"""
        logger.info("关闭抓取页 platform=%s", self.platform)
        await page.close()

    @abstractmethod
    async def search(self, ctx: CrawlContext, query: str) -> CrawlResult:
        """平台搜品：子类实现；开关页必须走 open_page/close_page。"""

    async def detail(self, ctx: CrawlContext, item_id: str) -> CrawlResult:
        """平台商品详情；默认未实现，仅支持的 Source 覆盖。"""
        raise AppError(
            "crawler.detail_unsupported",
            f"平台 {self.platform} 暂不支持商品详情",
            status_code=501,
        )
