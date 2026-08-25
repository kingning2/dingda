"""数据采集 — 闲鱼 / 1688 爬虫与浏览器会话。"""

from crawlers.alibaba.search import fetch_search as fetch_alibaba_search
from crawlers.factory import create_channel
from crawlers.xianyu.search import fetch_search as fetch_xianyu_search

__all__ = ["create_channel", "fetch_xianyu_search", "fetch_alibaba_search"]
