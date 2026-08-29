"""闲鱼渠道（参考 CowAgent weixin_channel 组织方式）。

组装闲鱼浏览器与扫码登录，供 ``create_channel("xianyu")`` 返回统一 Channel。"""

from __future__ import annotations

from typing import Any

from crawlers.channel import Channel
from crawlers.core.browser.base import BrowserPlatform
from crawlers.core.login.qrcode import QrcodeLogin
from crawlers.goofish.browser import XianyuBrowser
from crawlers.goofish.login.qrcode import XianyuQrcode


class XianyuChannel(Channel):
    """闲鱼：扫码 + Cookie 续期 + 滑块。"""

    def __init__(self) -> None:
        self._browser = XianyuBrowser()

    def browser(self) -> BrowserPlatform:
        return self._browser

    def qrcode(self) -> QrcodeLogin:
        return XianyuQrcode()

    async def renew_cookies(
        self,
        cookies: list[dict[str, Any]],
        *,
        account_id: str,
        punish_url: str | None = None,
        timeout_secs: int = 180,
    ) -> tuple[bool, str, dict[str, Any]]:
        from crawlers.goofish.login.cookie_renew import renew_cookies

        return await renew_cookies(
            cookies,
            account_id=account_id,
            punish_url=punish_url,
            platform=self.channel_type or "xianyu",
            timeout_secs=timeout_secs,
        )
