"""1688 搜索 MTOP 解析（对齐 1688-cli search-mtop.ts）。"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

SEARCH_MTOP_API = "mtop.relationrecommend.wirelessrecommend.recommend"
SEARCH_APP_ID = "32517"


def parse_mtop_jsonp(text: str) -> Any:
    trimmed = (text or "").strip()
    match = re.match(r"^mtopjsonp\w+\(([\s\S]*)\)$", trimmed)
    payload = match.group(1) if match else trimmed
    return json.loads(payload)


def _bool(value: Any) -> bool:
    return str(value).lower() == "true"


def _parse_count_text(text: Any) -> int | None:
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return int(text) if float(text) == int(text) else None
    if not text:
        return None
    compact = re.sub(r"\s+", "", str(text).replace(",", ""))
    match = re.search(r"(\d+(?:\.\d+)?)(万|w|W|亿|k|K)?", compact)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2) or ""
    multiplier = {
        "亿": 100_000_000,
        "万": 10_000,
        "w": 10_000,
        "W": 10_000,
        "k": 1_000,
        "K": 1_000,
    }.get(unit, 1)
    return int(round(value * multiplier))


def _text_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            if text:
                out.append(text)
    return out


def map_offer(item: dict[str, Any]) -> dict[str, Any] | None:
    data = item.get("data") if isinstance(item, dict) else None
    if not isinstance(data, dict):
        return None
    offer_id = str(data.get("offerId") or "").strip()
    if not offer_id:
        return None

    title = re.sub(r"</?font[^>]*>", "", str(data.get("title") or "")).strip()
    price_info = data.get("priceInfo") if isinstance(data.get("priceInfo"), dict) else {}
    price_raw = str(price_info.get("price") or "").strip()
    price = float(price_raw) if price_raw else None

    shop = data.get("shop") if isinstance(data.get("shop"), dict) else {}
    shop_add = data.get("shopAddition") if isinstance(data.get("shopAddition"), dict) else {}
    years_raw = str(shop.get("tpYear") or "").strip()
    years = int(years_raw) if years_raw.isdigit() else None

    tags = _text_list(data.get("tags"))
    service_tags = _text_list(data.get("serviceTags"))
    product_badges = _text_list(data.get("productBadges"))

    order_count_text = (
        data.get("orderCountText")
        or (str(data.get("orderCount")) if data.get("orderCount") is not None else None)
        or data.get("bookedCount")
    )
    repurchase_rate_text = data.get("repurchaseRateText") or data.get("repurchaseRate")

    offer: dict[str, Any] = {
        "offerId": offer_id,
        "title": title,
        "price": {
            "text": f"¥{price_raw}" if price_raw else "",
            "min": price,
            "max": price,
        },
        "supplier": {
            "name": shop.get("text"),
            "shopUrl": shop_add.get("shopLinkUrl") or data.get("winPortUrl"),
            "years": years,
        },
        "location": {
            "province": data.get("province"),
            "city": data.get("city"),
        },
        "bizType": data.get("bizType"),
        "verified": {
            "factory": _bool(data.get("factoryInspection")),
            "business": _bool(data.get("businessInspection")),
            "superFactory": _bool(data.get("superFactory")),
        },
        "tags": tags,
        "isP4P": _bool(data.get("isP4P")),
        "turnover": data.get("bookedCount"),
        "url": f"https://detail.1688.com/offer/{offer_id}.html",
        "image": data.get("offerPicUrl"),
    }
    if service_tags:
        offer["serviceTags"] = service_tags
    if product_badges:
        offer["productBadges"] = product_badges
    offer["demand"] = {
        "orderCountText": order_count_text,
        "orderCount": _parse_count_text(order_count_text),
        "repurchaseRateText": repurchase_rate_text,
        "repurchaseRate": None,
    }
    return offer


def read_search_mtop_request_meta(url: str) -> dict[str, Any] | None:
    if SEARCH_MTOP_API not in url:
        return None
    try:
        parsed = urlparse(url)
        data_param = parse_qs(parsed.query).get("data", [""])[0]
        if not data_param:
            return None
        data_obj = json.loads(data_param)
        params = json.loads(str(data_obj.get("params") or "{}"))
        begin_page = params.get("beginPage")
        return {
            "appId": str(data_obj.get("appId", "")),
            "method": params.get("method"),
            "beginPage": int(begin_page) if begin_page is not None else None,
            "sortType": params.get("sortType"),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def parse_offer_items_from_mtop_text(text: str) -> list[dict[str, Any]]:
    try:
        body = parse_mtop_jsonp(text)
    except json.JSONDecodeError:
        return []
    items = body.get("data", {}).get("data", {}).get("OFFER", {}).get("items", [])
    if not isinstance(items, list):
        return []
    offers: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        mapped = map_offer(item)
        if mapped:
            offers.append(mapped)
    return offers
