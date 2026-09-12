"""1688 找货 API 条目 → CrawlItem。

职责：
    将 gateway find.product 原始字段映射为标准化 CrawlItem；
    扩展字段放进 raw，供 compare Tool 使用。

设计说明：
    - 平台：ali1688；不依赖 Browser
"""

from __future__ import annotations

from typing import Any

from crawler.core.types import CrawlItem


def item_from_api(raw: dict[str, Any]) -> CrawlItem:
    """单条 API 商品 → CrawlItem。"""
    product_id = str(raw.get("itemId") or "")
    detail_url = raw.get("detailUrl") or (
        f"https://detail.1688.com/offer/{product_id}.html" if product_id else ""
    )
    price = raw.get("currentPrice")
    price_str = None if price is None else str(price)

    return CrawlItem(
        item_id=product_id,
        title=str(raw.get("title") or ""),
        url=str(detail_url),
        price=price_str,
        raw={
            "image_url": raw.get("imageUrl") or "",
            "similarity_score": float(raw.get("score") or 0),
            "sku_id": raw.get("skuId") or "",
            "sku_title": raw.get("skuTitle") or "",
            "yx_index": raw.get("yxIndex"),
            "quantity_begin": raw.get("quantityBegin"),
            "unit": raw.get("unit") or "",
            "supplier": raw.get("company") or "",
            "merchant_rating": _first_value(
                raw,
                "merchantRating",
                "sellerRating",
                "shopRating",
                "companyScore",
                "sellerScore",
            ),
            "repurchase_rate": _first_value(
                raw,
                "repurchaseRate",
                "repeatPurchaseRate",
            ),
            "sold_count": raw.get("soldOut") or 0,
            "stock_amount": raw.get("storeAmount") or 0,
            "user_id": str(raw.get("userId") or ""),
            "member_id": raw.get("memberId") or "",
            "category_id": raw.get("cateId"),
            "promotion_tags": raw.get("promotionTags") or [],
            "service_infos": raw.get("serviceInfos") or [],
            "selling_points": raw.get("sellingPoints") or [],
        },
    )


def items_from_api(rows: list[dict[str, Any]]) -> list[CrawlItem]:
    """批量映射，过滤无 id 的空行。"""
    out: list[CrawlItem] = []
    for row in rows:
        item = item_from_api(row)
        if item.item_id or item.title or item.url:
            out.append(item)
    return out


def _first_value(raw: dict[str, Any], *keys: str) -> Any:
    """返回首个非空原始字段，避免把未知字段硬编码成同名。"""
    for key in keys:
        value = raw.get(key)
        if value is not None and value != "":
            return value
    return None
