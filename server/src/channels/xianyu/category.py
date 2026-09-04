"""闲鱼类目 AI 识别。

职责：
    根据商品标题与图片调用 mtop 推荐发布类目；供 item.publish 前置使用。

设计说明：
    - 平台：闲鱼（xianyu）；需有效账号 cookie
    - 调用方：channels/xianyu/item.publish 等渠道流程
"""

from __future__ import annotations

import logging
from typing import Any

from src.channels.xianyu.mtop import call as mtop_call
from src.channels.xianyu.session import Session

logger = logging.getLogger("dingda.channel.xianyu.category")


def recommend(
    cookie: str,
    title: str,
    images: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """根据标题+图片识别类目。"""
    session = Session.from_cookie_header(cookie)
    images = images or []
    logger.info("recommend start title=%s images=%s", title[:40], len(images))
    image_infos: list[dict[str, Any]] = []
    for img in images:
        image_infos.append(
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
        )

    raw = mtop_call(
        session,
        api="mtop.taobao.idle.kgraph.property.recommend",
        data={
            "title": title,
            "lockCpv": False,
            "multiSKU": False,
            "publishScene": "mainPublish",
            "scene": "newPublishChoice",
            "description": title,
            "imageInfos": image_infos,
            "uniqueCode": "1775905618164677",
        },
        version="2.0",
        spm_cnt="a21ybx.publish.0.0",
        auto_refresh=False,
    )
    predict = (raw.get("data", {}) or {}).get("categoryPredictResult", {}) or {}
    result = {
        "cat_id": str(predict.get("catId", "")),
        "cat_name": predict.get("catName", ""),
        "channel_cat_id": str(predict.get("channelCatId", "")),
        "tb_cat_id": str(predict.get("tbCatId", "")),
        "confidence": predict.get("confidence", 0),
    }
    logger.info("recommend done cat_id=%s cat_name=%s", result["cat_id"], result["cat_name"])
    return result
