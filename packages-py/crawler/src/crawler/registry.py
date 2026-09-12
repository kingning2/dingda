"""按 platform 取出爬虫插头，避免业务里写 if。

职责：
    登记 BrowserCrawler / ApiCrawler 实现；给 Tool 注入平台 Cookie。

设计说明：
    - 新浏览器平台：sources/<id>/ + 本表 _BROWSER_SOURCES
    - 新 API 平台：sources/<id>/ + 本表 _API_SOURCES（不强制 BrowserPort）
    - Cookie 域名规则在 channels/<platform>/cookies，不进 Browser adapter
"""

from __future__ import annotations

from contracts.browser_port import BrowserPort, Cookie
from crawler.core.base import ApiCrawler, BrowserCrawler, BrowserSessionOptions
from crawler.sources.ali1688.crawler import Ali1688Crawler
from crawler.sources.xianyu.crawler import XianyuCrawler
from crawler.sources.xiaohongshu.crawler import XiaohongshuCrawler
from core.errors import AppError

_BROWSER_SOURCES: dict[str, type[BrowserCrawler]] = {
    "xianyu": XianyuCrawler,
    "xiaohongshu": XiaohongshuCrawler,
}

_API_SOURCES: dict[str, type[ApiCrawler]] = {
    "ali1688": Ali1688Crawler,
}


def is_api_platform(platform: str) -> bool:
    """是否为无浏览器的 API Source。"""
    return platform in _API_SOURCES


def create_crawler(
    platform: str,
    browser: BrowserPort,
    options: BrowserSessionOptions | None = None,
) -> BrowserCrawler:
    """按平台名创建浏览器 Source，并注入 BrowserPort。"""
    cls = _BROWSER_SOURCES.get(platform)
    if cls is None:
        if platform in _API_SOURCES:
            raise AppError(
                "crawler.platform_api_only",
                f"平台 {platform} 为 API 爬虫，请用 create_api_crawler",
            )
        raise AppError("crawler.platform_unsupported", f"不支持的爬虫平台：{platform}")
    return cls(browser, options)


def create_api_crawler(platform: str) -> ApiCrawler:
    """按平台名创建 API Source（不需要 Browser）。"""
    cls = _API_SOURCES.get(platform)
    if cls is None:
        raise AppError("crawler.platform_unsupported", f"不支持的 API 爬虫平台：{platform}")
    return cls()


def list_platforms() -> list[str]:
    """已注册平台名（浏览器 + API）。"""
    return sorted(set(_BROWSER_SOURCES) | set(_API_SOURCES))


def cookies_for(platform: str, cookie: str | None) -> list[Cookie] | None:
    """按平台插头转换 cookie；未知或 API 平台返回 None。"""
    cls = _BROWSER_SOURCES.get(platform)
    if cls is None:
        return None
    return cls.cookies_from_header(cookie)
