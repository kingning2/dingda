"""Crawler API 契约模型。

定义爬虫任务相关 HTTP 接口的数据结构。
字段命名与类型应与仓库根目录 ``contracts/schema/v1/crawler`` 保持一致，
便于三端（React / Rust 壳层 / Python）共享同一份 Schema 真相源。

当前模型：
    CrawlerTaskCreate  创建爬虫任务时的最小入参

后续扩展：
    任务状态、分页结果、Provider 枚举、错误码等。
"""

from __future__ import annotations

from pydantic import BaseModel


class CrawlerTaskCreate(BaseModel):
    """创建爬虫任务的请求体。"""

    provider: str
    query: str
