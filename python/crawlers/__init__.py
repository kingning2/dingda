"""数据采集包 — 闲鱼 / 1688 爬虫、登录与浏览器会话。

对外再导出各平台 search 入口与 ``create_channel`` 工厂。"""

from crawlers.alibaba.search import fetch_search as fetch_alibaba_search
from crawlers.factory import create_channel
from crawlers.xianyu.search import fetch_search as fetch_xianyu_search

__all__ = ["create_channel", "fetch_xianyu_search", "fetch_alibaba_search"]
