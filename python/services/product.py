"""商品归一化与跨平台匹配。

清洗标题/价格结构，并按规则把闲鱼与 1688 等结果配对。"""

from __future__ import annotations

import re
from typing import Any


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _to_product(item: dict[str, Any], *, platform: str) -> dict[str, Any]:
    title = str(item.get("title") or item.get("name") or "").strip()
    price = str(item.get("price") or item.get("price_text") or "").strip()
    url = str(item.get("url") or item.get("item_url") or "").strip()
    return {
        "platform": platform,
        "title": title,
        "title_key": _normalize_title(title),
        "price": price,
        "url": url,
        "raw": item,
    }


def normalize_products(
    xianyu_items: list[dict[str, Any]],
    alibaba_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for item in xianyu_items:
        title = str(item.get("title") or item.get("name") or "").strip()
        if title:
            products.append(_to_product(item, platform="xianyu"))
    for item in alibaba_items:
        title = str(item.get("title") or item.get("name") or "").strip()
        if title:
            products.append(_to_product(item, platform="alibaba"))
    return products


def match_products(normalized: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, list[dict[str, Any]]] = {}
    for product in normalized:
        key = str(product.get("title_key") or "")
        if not key:
            continue
        by_key.setdefault(key, []).append(product)

    matches: list[dict[str, Any]] = []
    for key, group in by_key.items():
        if len(group) < 2:
            continue
        platforms = {p.get("platform") for p in group}
        if len(platforms) >= 2:
            matches.append({"title_key": key, "items": group})
    return matches
