"""按 platform 取出爬虫插头，避免业务里写 if。

职责：
    登记 BrowserCrawler 实现；给 Tool 注入平台 Cookie。

设计说明：
    - 新平台只加 sources/<id>/ 并在本表登记
    - Cookie 域名规则在 channels/<platform>/cookies，不进 Browser adapter
"""

from __future__ import annotations

from src.browser.port import BrowserPort, Cookie
from src.crawler.core.base import BrowserCrawler, BrowserSessionOptions
from src.crawler.sources.xianyu.crawler import XianyuCrawler
from src.crawler.sources.xiaohongshu.crawler import XiaohongshuCrawler
from src.shared.errors import AppError

_SOURCES: dict[str, type[BrowserCrawler]] = {
    "xianyu": XianyuCrawler,
    "xiaohongshu": XiaohongshuCrawler,
}


def create_crawler(
    platform: str,
    browser: BrowserPort,
    options: BrowserSessionOptions | None = None,
) -> BrowserCrawler:
    """按平台名创建对应 Source，并注入 BrowserPort。"""
    cls = _SOURCES.get(platform)
    if cls is None:
        raise AppError("crawler.platform_unsupported", f"不支持的爬虫平台：{platform}")
    return cls(browser, options)


def list_platforms() -> list[str]:
    """已注册平台名。"""
    return sorted(_SOURCES)


def cookies_for(platform: str, cookie: str | None) -> list[Cookie] | None:
    """按平台插头转换 cookie；未知平台返回 None。"""
    cls = _SOURCES.get(platform)
    if cls is None:
        return None
    return cls.cookies_from_header(cookie)
