"""mtop 签名 — ``token&timestamp&appKey&data`` 的 MD5。

WebSocket token 请求与其它 H5 mtop 调用复用本函数生成 sign 参数。"""

from __future__ import annotations

import hashlib

from dingda_sidecar.crawlers.goofish.ws.constants import APP_KEY


def generate_sign(token: str, timestamp: str, data: str) -> str:
    msg = f"{token}&{timestamp}&{APP_KEY}&{data}"
    return hashlib.md5(msg.encode("utf-8")).hexdigest()  # noqa: S324
