"""mtop 签名。"""

from __future__ import annotations

import hashlib

from crawlers.xianyu.ws.constants import APP_KEY


def generate_sign(token: str, timestamp: str, data: str) -> str:
    msg = f"{token}&{timestamp}&{APP_KEY}&{data}"
    return hashlib.md5(msg.encode("utf-8")).hexdigest()  # noqa: S324
