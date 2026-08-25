"""通用工具包 — 网页搜索、浏览器探测等。

再导出 ``web_search`` / ``browser_available`` 供 Graph search 节点使用。"""

from tools.browser import browser_available
from tools.web_search import web_search

__all__ = ["browser_available", "web_search"]
