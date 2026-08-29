"""goofish（闲鱼）爬虫包 — 复用 vendored goofish_cli 方法 + 自定义实现。

搜索（Camoufox + goofish_cli DOM）、商品、资料、WebSocket 推送等平台能力，
供 mtop IPC、WSS 与 Graph 工具使用。见 crawlers/vendor/VENDOR.md。"""

from dingda_sidecar.crawlers.goofish.item import fetch_item_detail, fetch_seller_items
from dingda_sidecar.crawlers.goofish.profile import fetch_message_headinfo, fetch_user_profile
from dingda_sidecar.crawlers.goofish.search import fetch_search

__all__ = [
    "fetch_search",
    "fetch_seller_items",
    "fetch_item_detail",
    "fetch_user_profile",
    "fetch_message_headinfo",
]
