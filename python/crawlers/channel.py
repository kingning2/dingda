"""渠道抽象基类（参考 CowAgent channel/channel.py）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from crawlers.core.browser.base import BrowserPlatform
from crawlers.core.login.qrcode import QrcodeLogin


class Channel(ABC):
    """单个渠道的 Sidecar 能力入口；子类实现 browser / qrcode 等平台差异。"""

    channel_type: str = ""

    @abstractmethod
    def browser(self) -> BrowserPlatform:
        """Playwright 启动配置（UA / 代理 / 反检测）。"""

    @abstractmethod
    def qrcode(self) -> QrcodeLogin:
        """扫码登录实例。"""

    async def renew_cookies(
        self,
        cookies: list[dict[str, Any]],
        *,
        account_id: str,
        punish_url: str | None = None,
        timeout_secs: int = 180,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Cookie 浏览器续期；默认不支持，由子类覆写。"""
        return (
            False,
            f"渠道 {self.channel_type or 'unknown'} 暂不支持 Cookie 浏览器续期",
            {"status": "error"},
        )
