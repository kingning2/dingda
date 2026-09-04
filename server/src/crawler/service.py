"""爬虫任务编排入口（骨架）：按平台分发到 sources，经 BrowserPort 开页。

登录态维护属于 ``channels/``，本模块不负责扫码。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dingda.crawler")


class CrawlerService:
    """爬虫任务：创建、执行、查询（骨架，实现应调 create_crawler）。"""
