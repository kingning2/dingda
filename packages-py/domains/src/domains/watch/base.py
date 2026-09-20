"""商品监控取数插座。

职责：
    定义「按 platform + item_id 取一次商品详情」的统一接口，
    让 ``domains.watch`` 不必依赖 crawler / agent（插头由 ``api`` 挂载时注入）。

设计说明：
    - 插座：``ProductSnapshot``（归一后的取数结果）+ ``ProductFetcher``（协议）
    - 插头：当前未接线（原 ``api.watch_feed`` + 旧 ``tools.product`` 已删）；
      调度器要重新挂上时，在 ``api`` 用 ``agent/nodes`` 详情节点实现本协议
    - 价格文本不在这里解析：本层只搬事实，``poller`` 负责把文本收敛成数字
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from contracts.watch import SoldState


@dataclass(frozen=True, slots=True)
class ProductSnapshot:
    """一次商品详情抓取的归一结果。"""

    ok: bool
    price_text: str | None = None
    sold_state: str = SoldState.UNKNOWN
    status_text: str | None = None
    want_count: str | None = None
    browse_count: str | None = None
    title: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class ProductFetcher(Protocol):
    """取数插头协议：由 api 层注入具体实现。"""

    async def __call__(
        self,
        *,
        platform: str,
        item_id: str,
        cookie: str | None,
    ) -> ProductSnapshot:
        """取一次商品详情；失败不抛异常，用 ``ok=False`` + ``error_code`` 表达。"""
        ...
