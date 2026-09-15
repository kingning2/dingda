"""商品监控：价格解析与变更推导（纯函数，不碰库）。"""

from __future__ import annotations

from domains.watch.insight import (
    KIND_GONE,
    KIND_PRICE_DROP,
    KIND_PRICE_RISE,
    KIND_RELISTED,
    KIND_SOLD,
    derive_changes,
)
from domains.watch.poller import parse_price
from infrastructure.db.watch import WatchPointRow


def _point(
    price: float | None,
    sold_state: str,
    observed_at: float,
) -> WatchPointRow:
    """造一个价格点。"""
    return WatchPointRow(
        point_id=int(observed_at),
        target_id="watch-1",
        price=price,
        price_text=f"¥{price}" if price is not None else None,
        want_count=None,
        browse_count=None,
        status_text=None,
        sold_state=sold_state,
        observed_at=observed_at,
    )


def test_parse_price_handles_common_goofish_formats() -> None:
    assert parse_price("¥1,234.5") == 1234.5
    assert parse_price("¥1.2万") == 12000.0
    assert parse_price("88元") == 88.0
    assert parse_price("  ¥ 99 ") == 99.0


def test_parse_price_rejects_unparsable_and_non_positive() -> None:
    assert parse_price(None) is None
    assert parse_price("") is None
    assert parse_price("面议") is None
    assert parse_price("¥0") is None


def test_derive_changes_reports_price_drop_with_ratio() -> None:
    changes = derive_changes([_point(100.0, "on_sale", 1), _point(88.0, "on_sale", 2)])
    assert len(changes) == 1
    change = changes[0]
    assert change.kind == KIND_PRICE_DROP
    assert change.delta == -12.0
    assert change.delta_ratio == -0.12
    assert "降价" in change.message


def test_derive_changes_reports_price_rise() -> None:
    changes = derive_changes([_point(200.0, "on_sale", 1), _point(220.0, "on_sale", 2)])
    assert [c.kind for c in changes] == [KIND_PRICE_RISE]
    assert changes[0].delta == 20.0


def test_derive_changes_skips_unchanged_price() -> None:
    changes = derive_changes([_point(100.0, "on_sale", 1), _point(100.0, "on_sale", 2)])
    assert changes == []


def test_derive_changes_reports_sold_and_gone_once_each() -> None:
    points = [
        _point(100.0, "on_sale", 1),
        _point(100.0, "on_sale", 2),
        _point(100.0, "sold", 3),
    ]
    changes = derive_changes(points)
    assert [c.kind for c in changes] == [KIND_SOLD]
    assert "已售出" in changes[0].message

    gone = derive_changes([_point(100.0, "on_sale", 1), _point(None, "gone", 2)])
    assert [c.kind for c in gone] == [KIND_GONE]


def test_derive_changes_reports_relist_after_sold() -> None:
    """同一时刻先比价格、再比状态，所以降价事件排在重新在售之前。"""
    changes = derive_changes([_point(100.0, "sold", 1), _point(95.0, "on_sale", 2)])
    assert [c.kind for c in changes] == [KIND_PRICE_DROP, KIND_RELISTED]


def test_derive_changes_on_single_point_is_empty() -> None:
    assert derive_changes([_point(100.0, "on_sale", 1)]) == []
    assert derive_changes([]) == []
