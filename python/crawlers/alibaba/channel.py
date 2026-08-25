"""1688 渠道。"""

from __future__ import annotations

from crawlers.alibaba.browser import Ali1688Browser
from crawlers.alibaba.login.qrcode import Ali1688Qrcode
from crawlers.channel import Channel
from crawlers.core.browser.base import BrowserPlatform
from crawlers.core.login.qrcode import QrcodeLogin


class Ali1688Channel(Channel):
    """1688：扫码（含 SSO）；续期沿用基类默认「不支持」。"""

    def __init__(self) -> None:
        self._browser = Ali1688Browser()

    def browser(self) -> BrowserPlatform:
        return self._browser

    def qrcode(self) -> QrcodeLogin:
        return Ali1688Qrcode()
