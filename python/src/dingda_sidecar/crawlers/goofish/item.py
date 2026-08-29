"""闲鱼在售商品 / 详情拉取（mtop）。

调用 H5 mtop 拉取卖家在售列表与单品详情，并解析为统一字段供 IPC 返回。"""

from __future__ import annotations

import json
from typing import Any

from dingda_sidecar.crawlers.goofish.mtop import MtopClient, MtopRequest
from dingda_sidecar.crawlers.goofish.ws.cookies import my_id, parse_cookies

ITEM_URL_PREFIX = "https://www.goofish.com/item?id="


def fetch_seller_items(
    cookie_str: str,
    user_id: str,
    *,
    max_pages: int = 0,
) -> tuple[list[dict[str, Any]], str]:
    user_id = user_id.strip()
    if not user_id:
        raise ValueError("userId 不能为空")
    cookies = parse_cookies(cookie_str)
    if not my_id(cookies):
        raise ValueError("cookie 缺少 unb，无法拉取商品")

    client = MtopClient(cookie_str)
    page_limit = 50 if max_pages <= 0 else max_pages
    all_items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page_number in range(1, page_limit + 1):
        request = MtopRequest(
            api="mtop.idle.web.xyh.item.list",
            version="1.0",
            data={
                "userId": user_id,
                "pageNumber": page_number,
                "scene": "seller_home",
                "pageSize": 10,
            },
        )
        response = client.call(request)
        if not response.success():
            raise RuntimeError(f"商品列表接口未成功: {response.ret}")
        page_items = parse_list_page(response.data() or {})
        if not page_items:
            break
        added = 0
        for item in page_items:
            item_id = str(item.get("item_id") or "")
            if item_id and item_id not in seen:
                seen.add(item_id)
                all_items.append(item)
                added += 1
        if added == 0:
            break

    return all_items, client.cookie


def fetch_item_detail(cookie_str: str, item_id: str) -> tuple[dict[str, Any], str]:
    item_id = item_id.strip()
    if not item_id:
        raise ValueError("itemId 不能为空")
    cookies = parse_cookies(cookie_str)
    if not my_id(cookies):
        raise ValueError("cookie 缺少 unb，无法拉取商品详情")

    client = MtopClient(cookie_str)
    request = MtopRequest(
        api="mtop.taobao.idle.pc.detail",
        version="1.0",
        data={"itemId": item_id},
    )
    response = client.call(request)
    if not response.success():
        raise RuntimeError(f"商品详情接口未成功: {response.ret}")
    detail = parse_item_detail(response.data() or {}, item_id)
    return detail, client.cookie


def parse_list_page(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    entries = data.get("cardList") or data.get("items")
    if not isinstance(entries, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        parsed = parse_list_item(entry)
        if parsed:
            out.append(parsed)
    return out


def parse_list_item(entry: dict[str, Any]) -> dict[str, Any] | None:
    item_id = _extract_item_id(entry)
    if not item_id:
        return None
    return {
        "item_id": item_id,
        "title": _extract_title(entry),
        "price": _extract_price(entry),
        "desc": "",
    }


def parse_item_detail(data: Any, item_id: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("商品详情响应缺少 itemDO")
    item_do = data.get("itemDO")
    if not isinstance(item_do, dict):
        raise ValueError("商品详情响应缺少 itemDO")

    title = _text_field(item_do, "title") or ""
    desc = _text_field(item_do, "desc") or ""
    images = _extract_image_urls(item_do)

    share_json = (
        (item_do.get("shareData") or {}).get("shareInfoJsonString")
        if isinstance(item_do.get("shareData"), dict)
        else None
    )
    if isinstance(share_json, str) and share_json.strip():
        try:
            inner = json.loads(share_json)
        except json.JSONDecodeError:
            inner = None
        if isinstance(inner, dict):
            main_params = (
                (inner.get("contentParams") or {}).get("mainParams")
                if isinstance(inner.get("contentParams"), dict)
                else inner
            )
            if isinstance(main_params, dict):
                content = _text_field(main_params, "content")
                if content:
                    desc = content
                share_images = main_params.get("images")
                if isinstance(share_images, list):
                    urls = []
                    for entry in share_images:
                        if not isinstance(entry, dict):
                            continue
                        url = entry.get("image") or entry.get("url")
                        if isinstance(url, str) and url.strip():
                            urls.append(url.strip())
                    if urls:
                        images = urls

    if not title:
        title = desc.splitlines()[0].strip() if desc else ""

    price = _parse_price(item_do.get("soldPrice"))
    if price is None:
        price_info = item_do.get("priceInfo")
        if isinstance(price_info, dict):
            price = _parse_price(price_info.get("price"))
    if price is None:
        price = 0.0

    return {
        "item_id": item_id,
        "title": title,
        "desc": desc,
        "price": price,
        "original_price": _parse_price(item_do.get("originalPrice")),
        "images": images,
        "want_count": _u32_field(item_do, "wantCnt", "wantCount"),
        "browse_count": _u32_field(item_do, "browseCnt", "browseCount"),
        "item_url": f"{ITEM_URL_PREFIX}{item_id}",
    }


def _pointer(obj: Any, *keys: str) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_item_id(entry: dict[str, Any]) -> str | None:
    for path in (
        ("cardData", "detailParams", "itemId"),
        ("data", "itemId"),
        ("itemId",),
    ):
        value = _pointer(entry, *path)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_title(entry: dict[str, Any]) -> str:
    for path in (
        ("cardData", "main", "title"),
        ("cardData", "detailParams", "title"),
        ("data", "title"),
        ("title",),
    ):
        value = _pointer(entry, *path)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_price(entry: dict[str, Any]) -> float:
    paths = (
        ("cardData", "main", "soldPrice"),
        ("cardData", "detailParams", "soldPrice"),
        ("data", "soldPrice"),
        ("soldPrice",),
        ("cardData", "main", "price"),
        ("price",),
    )
    for path in paths:
        value = _pointer(entry, *path)
        parsed = _parse_price(value)
        if parsed is not None:
            return parsed
    return 0.0


def _parse_price(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _text_field(obj: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _u32_field(obj: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                continue
    return None


def _extract_image_urls(item_do: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    infos = item_do.get("imageInfos")
    if isinstance(infos, list):
        for entry in infos:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url") or entry.get("image")
            if isinstance(url, str) and url.strip():
                urls.append(url.strip())
    return urls
