"""闲鱼关键词搜索包。

再导出 ``fetch_search``，供 channel search handler 与 Graph 工具使用。"""

from crawlers.xianyu.search.fetch import fetch_search

__all__ = ["fetch_search"]
