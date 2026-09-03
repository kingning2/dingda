"""Crawler 领域服务。

职责：
    管理爬虫任务的完整生命周期：
    - 按 Provider（闲鱼、Mock 等）分发任务
    - 执行搜索、详情抓取、登录态维护
    - 发布领域事件（进度、结果、错误）供前端订阅

迁移来源：
    旧版 ``dingda_sidecar.runtime.crawler`` 与 ``dingda_sidecar.crawlers``

目录规划（待建）：
    providers/   各平台爬虫实现
    models.py    任务、结果等领域模型
    events.py    爬虫领域事件定义

设计约定：
    - Provider 通过抽象基类注册，便于扩展新平台
    - 浏览器自动化相关代码逐步从 vendor 目录迁入
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dingda.crawler")


class CrawlerService:
    """爬虫应用服务：创建、执行、查询爬虫任务。"""

    # 从 dingda_sidecar.runtime.crawler + crawlers/ 迁移实现
