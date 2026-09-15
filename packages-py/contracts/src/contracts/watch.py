"""商品监控共享词表。

职责：
    定义「被监控商品」在采集端与业务端之间传递的两个状态词表：
    商品售出态 ``SoldState`` 与监控开关态 ``WatchState``。

设计说明：
    - crawler 产出售出态、tools 透传、domains.watch 消费，三包都依赖 contracts，
      所以词表放这里，避免各方各写一套字符串
    - 值即落库值（``watch_targets.state`` / ``sold_state``）。改值等于改数据，
      必须配迁移，不能只改枚举
    - 售出态的关键词映射属平台知识，在 ``crawler/sources/<platform>/extract.json``，
      不在本模块

使用示例：
    from contracts.watch import SoldState, WatchState
    if row.sold_state == SoldState.SOLD:
        ...
"""

from __future__ import annotations

from enum import StrEnum


class SoldState(StrEnum):
    """商品当前是否还能买到。"""

    UNKNOWN = "unknown"
    """状态文案未命中任何关键词，或还没轮询过。"""

    ON_SALE = "on_sale"
    """在售，可以买到。"""

    SOLD = "sold"
    """已售出——需求被验证的信号。"""

    DELISTED = "delisted"
    """卖家主动下架（未成交）。"""

    GONE = "gone"
    """详情已取不到（商品不存在），通常是售出或彻底删除。"""


class WatchState(StrEnum):
    """监控任务本身的开关。"""

    ACTIVE = "active"
    """正在按间隔轮询。"""

    PAUSED = "paused"
    """暂停轮询，保留价格历史。"""

    ARCHIVED = "archived"
    """已归档，不再轮询。"""


def is_finished(sold_state: str) -> bool:
    """商品是否已结束生命周期（售出 / 下架 / 消失），结束就不必再高频轮询。"""
    return sold_state in (SoldState.SOLD, SoldState.DELISTED, SoldState.GONE)
