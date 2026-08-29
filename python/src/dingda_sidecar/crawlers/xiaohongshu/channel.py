"""小红书渠道实现。

组装浏览器与扫码登录能力，供 ``create_channel("xiaohongshu")`` 返回统一 Channel 接口。
搜索走双通道（mcp 优先 / Camoufox 回退），见 crawlers/vendor/VENDOR.md。"""

from __future__ import annotations

from dingda_sidecar.crawlers.channel import Channel
from dingda_sidecar.crawlers.core.browser.base import BrowserPlatform
from dingda_sidecar.crawlers.core.login.qrcode import QrcodeLogin
from dingda_sidecar.crawlers.xiaohongshu.browser import XiaohongshuBrowser
from dingda_sidecar.crawlers.xiaohongshu.login.qrcode import XiaohongshuQrcode


class XiaohongshuChannel(Channel):
    """小红书：扫码登录 + 搜索双通道。"""

    def __init__(self) -> None:
        self._browser = XiaohongshuBrowser()

    def browser(self) -> BrowserPlatform:
        return self._browser

    def qrcode(self) -> QrcodeLogin:
        return XiaohongshuQrcode()
