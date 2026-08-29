"""小红书扫码登录。

基于核心 ``QrcodeLogin``，绑定小红书浏览器配置完成取码、轮询与 Cookie 导出。
登录页 QR 选择器为猜测值（见 platform_config），需实机校准。"""

from __future__ import annotations

from dingda_sidecar.crawlers.core.login.qrcode import QrcodeLogin
from dingda_sidecar.crawlers.xiaohongshu.browser import XiaohongshuBrowser


class XiaohongshuQrcode(QrcodeLogin):
    """小红书扫码；无额外 hook 时使用基类默认流程。"""

    def __init__(self) -> None:
        super().__init__(XiaohongshuBrowser())
