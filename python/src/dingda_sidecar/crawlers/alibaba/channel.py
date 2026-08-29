"""1688 渠道实现。

组装浏览器与扫码登录能力，供 ``create_channel("ali1688")`` 返回统一 Channel 接口。"""

from __future__ import annotations

from dingda_sidecar.crawlers.alibaba.browser import Ali1688Browser
from dingda_sidecar.crawlers.alibaba.login.qrcode import Ali1688Qrcode
from dingda_sidecar.crawlers.channel import Channel
from dingda_sidecar.crawlers.core.browser.base import BrowserPlatform
from dingda_sidecar.crawlers.core.login.qrcode import QrcodeLogin


class Ali1688Channel(Channel):
    """1688：扫码（含 SSO）；续期沿用基类默认「不支持」。"""

    def __init__(self) -> None:
        self._browser = Ali1688Browser()

    def browser(self) -> BrowserPlatform:
        return self._browser

    def qrcode(self) -> QrcodeLogin:
        return Ali1688Qrcode()
