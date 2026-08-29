"""闲鱼扫码登录。

基于核心 ``QrcodeLogin``，绑定闲鱼浏览器配置完成取码、轮询与 Cookie 导出。"""

from __future__ import annotations

from crawlers.core.login.qrcode import QrcodeLogin
from crawlers.goofish.browser import XianyuBrowser


class XianyuQrcode(QrcodeLogin):
    """闲鱼扫码；无额外 hook 时使用基类默认流程。"""

    def __init__(self) -> None:
        super().__init__(XianyuBrowser())
