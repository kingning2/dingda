"""数据采集包 — 闲鱼 / 1688 / 小红书 渠道爬虫（通用网页见 tools.web）。

闲鱼搜索走系统 Camoufox + goofish_cli DOM；小红书走 vendored xhs-cli。
见 crawlers/vendor/VENDOR.md。"""

from dingda_sidecar.crawlers.alibaba.search import fetch_search as fetch_alibaba_search
from dingda_sidecar.crawlers.factory import create_channel
from dingda_sidecar.crawlers.goofish.search import fetch_search as fetch_xianyu_search
from dingda_sidecar.crawlers.xiaohongshu.search import fetch_search as fetch_xiaohongshu_search

__all__ = [
    "create_channel",
    "fetch_alibaba_search",
    "fetch_xianyu_search",
    "fetch_xiaohongshu_search",
]
