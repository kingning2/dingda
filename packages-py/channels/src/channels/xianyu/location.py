"""闲鱼默认发布地址（POI）。

职责：
    按经纬度拉取账号默认发布省市区与 POI；供 publish 填充地址字段。

设计说明：
    - 平台：闲鱼（xianyu）
    - 调用方：channels/xianyu/item.publish 等渠道流程
"""

from __future__ import annotations

import logging
from typing import Any

from channels.xianyu.mtop import call as mtop_call
from channels.xianyu.session import Session

logger = logging.getLogger("dingda.channel.xianyu.location")


def default(
    cookie: str,
    *,
    longitude: float = 121.4737,
    latitude: float = 31.2304,
) -> dict[str, Any]:
    """获取账号默认发布地址。"""
    session = Session.from_cookie_header(cookie)
    logger.info("location start lon=%s lat=%s", longitude, latitude)
    raw = mtop_call(
        session,
        api="mtop.taobao.idle.local.poi.get",
        data={"longitude": longitude, "latitude": latitude},
        version="1.0",
        spm_cnt="a21ybx.publish.0.0",
        auto_refresh=False,
    )
    data = raw.get("data", {}) or {}
    addrs = data.get("commonAddresses", []) or []
    selected = data.get("selectedPoi") or (addrs[0] if addrs else None)
    if not selected:
        return {
            "prov": "",
            "city": "",
            "area": "",
            "poi": "",
            "division_id": "",
            "all": [],
        }
    result = {
        "prov": selected.get("prov", ""),
        "city": selected.get("city", ""),
        "area": selected.get("area", ""),
        "poi": selected.get("poi", ""),
        "division_id": str(selected.get("divisionId", "")),
        "all": addrs or [selected],
    }
    logger.info("location done city=%s poi=%s", result["city"], result["poi"])
    return result
