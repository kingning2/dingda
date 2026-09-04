"""爬虫核心类型：任务上下文与抓取结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CrawlContext:
    """一次抓取任务的运行上下文。"""

    task_id: str
    account_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrawlItem:
    """标准化后的单条抓取结果（平台无关字段）。"""

    item_id: str
    title: str
    url: str
    price: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CrawlResult:
    """一次 search / detail 的产出。"""

    items: list[CrawlItem] = field(default_factory=list)
    raw_html: str | None = None
