"""闲鱼扫码登录。"""

from __future__ import annotations

from crawlers.core.login.qrcode import QrcodeLogin
from crawlers.xianyu.browser import XianyuBrowser


class XianyuQrcode(QrcodeLogin):
    """闲鱼扫码；无额外 hook 时使用基类默认流程。"""

    def __init__(self) -> None:
        super().__init__(XianyuBrowser())
