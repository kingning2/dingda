"""闲鱼搜索 MTOP 解析（对齐 ai-goofish-monitor parsers._parse_search_results_json）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

SEARCH_API_FRAGMENT = "/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/"


def is_search_results_response(response: Any) -> bool:
    request = getattr(response, "request", None)
    method = getattr(request, "method", None)
    url = str(getattr(response, "url", "") or "")
    if SEARCH_API_FRAGMENT not in url:
        return False
    if "search.shade" in url:
        return False
    return method == "POST"


def _safe_get(data: Any, *keys: str, default: Any = None) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _join_price_parts(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
    return text.replace("当前价", "").strip()


def _normalize_price(price: str) -> str:
    value = price.strip()
    if not value:
        return ""
    if "万" in value:
        raw = value.replace("¥", "").replace("万", "").strip()
        try:
            return f"¥{float(raw) * 10000:.0f}"
        except ValueError:
            return value
    return value if value.startswith("¥") else f"¥{value}" if value else ""


def _format_publish_time(raw: Any) -> str:
    text = str(raw or "").strip()
    if text.isdigit():
        return datetime.fromtimestamp(int(text) / 1000).strftime("%Y-%m-%d %H:%M")
    return text or ""


def _normalize_item_url(raw: str) -> str:
    link = (raw or "").strip()
    if not link:
        return ""
    if link.startswith("fleamarket://"):
        return link.replace("fleamarket://", "https://www.goofish.com/")
    return link


def map_item(entry: dict[str, Any]) -> dict[str, Any] | None:
    main = _safe_get(entry, "data", "item", "main", default={})
    if not isinstance(main, dict):
        return None
    ex_content = _safe_get(main, "exContent", default={})
    if not isinstance(ex_content, dict):
        return None
    click_params = _safe_get(main, "clickParam", "args", default={})
    if not isinstance(click_params, dict):
        click_params = {}

    item_id = str(_safe_get(ex_content, "itemId", default="")).strip()
    title = str(_safe_get(ex_content, "title", default="")).strip()
    if not item_id or not title:
        return None

    price_text = _normalize_price(_join_price_parts(_safe_get(ex_content, "price", default=[])))
    original_price = str(_safe_get(ex_content, "oriPrice", default="")).strip()
    area = str(_safe_get(ex_content, "area", default="")).strip()
    seller = str(_safe_get(ex_content, "userNickName", default="")).strip()
    image = str(_safe_get(ex_content, "picUrl", default="")).strip()
    raw_link = str(_safe_get(main, "targetUrl", default="")).strip()
    url = _normalize_item_url(raw_link) or f"https://www.goofish.com/item?id={item_id}"

    tags: list[str] = []
    if str(click_params.get("tag") or "") == "freeship":
        tags.append("包邮")
    fish_tags = _safe_get(ex_content, "fishTags", "r1", "tagList", default=[])
    if isinstance(fish_tags, list):
        for tag_item in fish_tags:
            content = str(_safe_get(tag_item, "data", "content", default="")).strip()
            if content and content not in tags:
                tags.append(content)

    want_count = click_params.get("wantNum")
    want_text = str(want_count).strip() if want_count is not None else ""

    item: dict[str, Any] = {
        "itemId": item_id,
        "title": title,
        "url": url,
        "price": {
            "text": price_text,
            **({"original": original_price} if original_price else {}),
        },
        "location": area,
        "seller": {"name": seller} if seller else {},
        "wantCount": want_text,
        "publishedAt": _format_publish_time(click_params.get("publishTime")),
    }
    if image:
        item["image"] = image
    if tags:
        item["tags"] = tags
    return item


def parse_search_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result_list = _safe_get(payload, "data", "resultList", default=[])
    if not isinstance(result_list, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in result_list:
        if not isinstance(entry, dict):
            continue
        mapped = map_item(entry)
        if mapped:
            items.append(mapped)
    return items
