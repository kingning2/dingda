"""闲鱼商品：在售列表、下架与发布。

职责：
    封装 mtop 商品管理 API；发布流程串联 category、location、media。

设计说明：
    - 平台：闲鱼（xianyu）；需账号 cookie
    - 调用方：账号 / 渠道 HTTP，非 MCP Tool
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from channels.xianyu.category import recommend
from channels.xianyu.guard import hold
from channels.xianyu.limiter import acquire
from channels.xianyu.location import default as default_location
from channels.xianyu.media import upload
from channels.xianyu.mtop import call as mtop_call
from channels.xianyu.session import Session

logger = logging.getLogger("dingda.channel.xianyu.item")

MAX_LIMIT = 100
DEFAULT_PAGE_SIZE = 20
MAX_PAGES = 50
STATUS_MAP = {"0": "在售", "1": "已下架"}


def _normalize_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return min(MAX_LIMIT, max(1, n))


def extract(card_data: dict[str, Any]) -> dict[str, Any]:
    """从 cardData 提取商品关键字段。"""
    item_id = str(card_data.get("id", ""))
    title = card_data.get("title", "")
    price_info = card_data.get("priceInfo") or {}
    price = (price_info.get("preText") or "") + str(price_info.get("price") or "")
    status_code = str(card_data.get("itemStatus", ""))
    status = STATUS_MAP.get(status_code, status_code)
    pic_info = card_data.get("picInfo") or {}
    image_url = pic_info.get("picUrl", "")
    labels: list[str] = []
    label_vo = card_data.get("itemLabelDataVO") or {}
    if isinstance(label_vo, dict):
        label_data = label_vo.get("labelData") or {}
        for _region, region_data in label_data.items():
            for tag in (region_data.get("tagList") if isinstance(region_data, dict) else []) or []:
                tag_data = tag.get("data") if isinstance(tag, dict) else None
                if not isinstance(tag_data, dict) or tag_data.get("type") == "img":
                    continue
                content = tag_data.get("content")
                if content:
                    labels.append(content)
    return {
        "item_id": item_id,
        "title": title,
        "price": price,
        "status": status,
        "image_url": image_url,
        "tags": labels,
    }


def items(cookie: str, *, limit: int = 50) -> dict[str, Any]:
    """查看当前账号在售商品。"""
    session = Session.from_cookie_header(cookie)
    n = _normalize_limit(limit)
    logger.info("items start limit=%s", n)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    page_number = 1

    def _add(card_data: dict[str, Any]) -> None:
        row = extract(card_data)
        if row["item_id"] and row["item_id"] not in seen:
            seen.add(row["item_id"])
            out.append(row)

    while len(out) < n and page_number <= MAX_PAGES:
        raw = mtop_call(
            session,
            api="mtop.idle.web.xyh.item.list",
            data={
                "needGroupInfo": True,
                "pageNumber": page_number,
                "userId": session.unb,
                "pageSize": DEFAULT_PAGE_SIZE,
            },
            version="1.0",
            spm_cnt="a21ybx.item.0.0",
            auto_refresh=False,
        )
        data = raw.get("data", {}) or {}
        before = len(out)

        if page_number == 1:
            top = data.get("topItem")
            if isinstance(top, dict) and top:
                _add(top.get("cardData") or top)

        for card in data.get("cardList") or []:
            _add(card.get("cardData") or card)

        if len(out) == before or not data.get("nextPage"):
            break
        page_number += 1

    rows = out[:n]
    for index, row in enumerate(rows):
        row["rank"] = index + 1
    logger.info("items done total=%s", len(rows))
    return {"items": rows, "total": len(rows)}


def delete(cookie: str, item_id: str) -> dict[str, Any]:
    """下架/删除商品。"""
    session = Session.from_cookie_header(cookie)
    logger.info("delete start item_id=%s", item_id)
    with acquire("item.write"), hold():
        raw = mtop_call(
            session,
            api="com.taobao.idle.item.delete",
            data={"itemId": str(item_id)},
            version="1.1",
            spm_cnt="a21ybx.item.0.0",
            auto_refresh=False,
        )
    ret = raw.get("ret") or []
    ok = any("SUCCESS" in str(r) for r in ret)
    logger.info("delete done item_id=%s ok=%s", item_id, ok)
    return {
        "item_id": str(item_id),
        "ok": ok,
        "message": " | ".join(str(r) for r in ret),
    }


def publish(
    cookie: str,
    *,
    title: str,
    desc: str,
    images: list[str],
    price: float,
    original_price: float | None = None,
    delivery: Literal["包邮", "按距离计费", "一口价", "无需邮寄"] = "无需邮寄",
    post_price: float = 0,
    can_self_pickup: bool = True,
) -> dict[str, Any]:
    """发布商品：upload → category → location → mtop publish。"""
    session = Session.from_cookie_header(cookie)
    logger.info("publish start title=%s images=%s", title[:40], len(images))

    image_infos: list[dict[str, Any]] = []
    for path in images:
        uploaded = upload(cookie, path)
        image_infos.append(
            {
                "url": uploaded["url"],
                "width": uploaded["width"],
                "height": uploaded["height"],
            }
        )

    cat = recommend(cookie, title, image_infos)
    loc = default_location(cookie)
    data = _build_publish_data(
        title=title,
        desc=desc,
        image_infos=image_infos,
        price=price,
        original_price=original_price,
        delivery=delivery,
        post_price=post_price,
        can_self_pickup=can_self_pickup,
        cat_info=cat,
        location=loc,
    )
    with acquire("item.write"), hold():
        raw = mtop_call(
            session,
            api="mtop.idle.pc.idleitem.publish",
            data=data,
            version="1.0",
            spm_cnt="a21ybx.publish.0.0",
            auto_refresh=False,
        )
    data_out = raw.get("data", {}) or {}
    ok = any("SUCCESS" in str(r) for r in raw.get("ret", []))
    logger.info("publish done ok=%s item_id=%s", ok, data_out.get("itemId", ""))
    return {
        "item_id": data_out.get("itemId", ""),
        "title": title,
        "price": price,
        "cat_name": cat.get("cat_name", ""),
        "ok": ok,
    }


def _build_publish_data(
    *,
    title: str,
    desc: str,
    image_infos: list[dict[str, Any]],
    price: float,
    original_price: float | None,
    delivery: str,
    post_price: float,
    can_self_pickup: bool,
    cat_info: dict[str, Any],
    location: dict[str, Any],
) -> dict[str, Any]:
    image_do_list = [
        {
            "extraInfo": {"isH": "false", "isT": "false", "raw": "false"},
            "isQrCode": False,
            "url": img["url"],
            "heightSize": img["height"],
            "widthSize": img["width"],
            "major": True,
            "type": 0,
            "status": "done",
        }
        for img in image_infos
    ]

    post_fee: dict[str, Any] = {
        "canFreeShipping": False,
        "supportFreight": False,
        "onlyTakeSelf": False,
    }
    if delivery == "包邮":
        post_fee["canFreeShipping"] = True
        post_fee["supportFreight"] = True
    elif delivery == "按距离计费":
        post_fee["supportFreight"] = True
        post_fee["templateId"] = "-100"
    elif delivery == "一口价":
        post_fee["supportFreight"] = True
        post_fee["postPriceInCent"] = str(int(post_price * 100))
        post_fee["templateId"] = "0"
    elif delivery == "无需邮寄":
        post_fee["templateId"] = "0"

    price_dto: dict[str, str] = {}
    default_price = price <= 0
    if not default_price:
        price_dto["priceInCent"] = str(int(price * 100))
    if original_price and original_price > 0:
        price_dto["origPriceInCent"] = str(int(original_price * 100))

    item_addr: dict[str, Any] = {}
    if location.get("division_id"):
        all_addrs = location.get("all", []) or []
        first = all_addrs[0] if all_addrs else {}
        item_addr = {
            "area": first.get("area", ""),
            "city": first.get("city", ""),
            "divisionId": first.get("divisionId", ""),
            "gps": f"{first.get('longitude', '')},{first.get('latitude', '')}",
            "poiId": first.get("poiId", ""),
            "poiName": first.get("poi", ""),
            "prov": first.get("prov", ""),
        }

    return {
        "freebies": False,
        "itemTypeStr": "b",
        "quantity": "1",
        "simpleItem": "true",
        "imageInfoDOList": image_do_list,
        "itemTextDTO": {"desc": desc, "title": title, "titleDescSeparate": True},
        "itemLabelExtList": [],
        "itemPriceDTO": price_dto,
        "userRightsProtocols": [{"enable": False, "serviceCode": "SKILL_PLAY_NO_MIND"}],
        "itemPostFeeDTO": post_fee,
        "itemAddrDTO": item_addr,
        "defaultPrice": default_price,
        "itemCatDTO": {
            "catId": cat_info["cat_id"],
            "catName": cat_info["cat_name"],
            "channelCatId": cat_info["channel_cat_id"],
            "tbCatId": cat_info["tb_cat_id"],
        },
        "onlyTakeSelf": can_self_pickup,
        "uniqueCode": "1775897582791680",
        "sourceId": "pcMainPublish",
        "bizcode": "pcMainPublish",
        "publishScene": "pcMainPublish",
    }
