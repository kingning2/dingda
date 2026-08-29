"""小红书爬虫包 — 走 vendored xhs-cli（XhsClient，系统 Camoufox）。

登录态由账号库 Cookie 注入；搜索见 crawlers/vendor/VENDOR.md。"""

from dingda_sidecar.crawlers.xiaohongshu.search import fetch_search

__all__ = ["fetch_search"]
