"""浏览器会话：从 Port 开一页，退出时自动关闭。"""

from __future__ import annotations

import logging

from browser.context import ContextOptions
from contracts.browser_port import BrowserPort, Page

logger = logging.getLogger("dingda.browser.session")


class BrowserSession:
    """一次操作会话：async with 拿到 Page，离开时 close。"""

    def __init__(
        self,
        port: BrowserPort,
        options: ContextOptions | None = None,
    ) -> None:
        self._port = port
        self._options = options or ContextOptions()
        self._page: Page | None = None

    async def __aenter__(self) -> Page:
        """打开带代理/指纹/Cookie 的一页。"""
        opts = self._options
        logger.info(
            "打开会话页 engine=%s proxy=%s fingerprint=%s",
            self._port.engine,
            bool(opts.proxy_url),
            opts.fingerprint_profile,
        )
        self._page = await self._port.open(
            proxy=opts.proxy_url,
            fingerprint=opts.fingerprint_profile,
            cookies=opts.cookies,
            default_domain=opts.default_cookie_domain,
        )
        return self._page

    async def __aexit__(self, *exc: object) -> None:
        """关闭本会话页。"""
        if self._page is None:
            return
        logger.info("关闭会话页 engine=%s", self._port.engine)
        await self._page.close()
        self._page = None
