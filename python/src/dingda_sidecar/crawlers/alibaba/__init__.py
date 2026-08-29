"""1688 爬虫包。

导出关键词搜索等平台能力，供 sidecar channel handler 与 Graph 工具调用。"""

from dingda_sidecar.crawlers.alibaba.search import fetch_search

__all__ = ["fetch_search"]
