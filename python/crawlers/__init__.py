"""数据采集包 — 闲鱼 / 1688 渠道爬虫（通用网页见 tools.web）。"""

from crawlers.alibaba.search import fetch_search as fetch_alibaba_search
from crawlers.factory import create_channel
from crawlers.xianyu.search import fetch_search as fetch_xianyu_search

__all__ = [
    "create_channel",
    "fetch_alibaba_search",
    "fetch_xianyu_search",
]
