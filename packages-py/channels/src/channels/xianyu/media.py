"""闲鱼图片上传至 CDN。

职责：
    将本地图片 multipart 上传到 stream-upload.goofish.com；返回 url 与尺寸元数据。

设计说明：
    - 平台：闲鱼（xianyu）
    - 调用方：channels/xianyu/item.publish 等渠道流程
"""

from __future__ import annotations

import logging
import os
from typing import Any

from channels.xianyu.limiter import acquire
from channels.xianyu.session import USER_AGENT, Session
from core.errors import AppError

logger = logging.getLogger("dingda.channel.xianyu.media")

UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"


def upload(cookie: str, path: str) -> dict[str, Any]:
    """上传图片，返回 url / width / height / size。"""
    session = Session.from_cookie_header(cookie)
    abs_path = os.path.expanduser(path)
    if not os.path.exists(abs_path):
        raise AppError("media.not_found", f"图片不存在：{abs_path}", status_code=404)

    logger.info("upload start path=%s", abs_path)
    headers = {
        "accept": "*/*",
        "origin": "https://www.goofish.com",
        "referer": "https://www.goofish.com/",
        "user-agent": USER_AGENT,
    }
    params = {"floderId": "0", "appkey": "xy_chat", "_input_charset": "utf-8"}
    with acquire("item.write"):
        with open(abs_path, "rb") as handle:
            resp = session.http.post(
                UPLOAD_URL,
                headers=headers,
                params=params,
                files={"file": (os.path.basename(abs_path), handle, "image/png")},
                timeout=60,
            )
    raw = resp.json()
    obj = raw.get("object") or {}
    pix = str(obj.get("pix", "0x0"))
    try:
        width, height = map(int, pix.split("x"))
    except ValueError:
        width = height = 0
    result = {
        "url": obj.get("url", ""),
        "width": width,
        "height": height,
        "size": obj.get("size", 0),
    }
    logger.info("upload done url=%s", result["url"][:80] if result["url"] else "")
    return result
