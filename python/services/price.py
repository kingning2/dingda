"""比价服务 — 解析价格字段并比较高低。

为匹配后的商品对提供简单数值比价，供分析节点引用。"""

from __future__ import annotations

import re
from typing import Any


def _parse_price(value: str) -> float | None:
    digits = re.sub(r"[^\d.]", "", value)
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def compare_prices(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    for match in matches:
        items = match.get("items") or []
        priced: list[tuple[dict[str, Any], float]] = []
        for item in items:
            price = _parse_price(str(item.get("price") or ""))
            if price is not None:
                priced.append((item, price))
        if len(priced) < 2:
            continue
        priced.sort(key=lambda pair: pair[1])
        low_item, low_price = priced[0]
        high_item, high_price = priced[-1]
        comparisons.append(
            {
                "title_key": match.get("title_key"),
                "lowest": {"platform": low_item.get("platform"), "price": low_price},
                "highest": {"platform": high_item.get("platform"), "price": high_price},
                "spread": round(high_price - low_price, 2),
            },
        )
    return comparisons
