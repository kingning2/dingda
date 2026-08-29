"""小红书 Playwright 浏览器配置（扫码登录用）。

基类 `QrcodeLogin` 走 Playwright chromium（系统 Edge/Chrome）取码与轮询；
本模块提供平台 UA / 代理 / 反检测配置。"""

from __future__ import annotations

import logging
import os
from typing import Any

from dingda_sidecar.crawlers.core.browser.base import BrowserPlatform
from dingda_sidecar.crawlers.core.playwright_common import CHROME_DESKTOP_UA, inject_init_script

_ANTI_DETECT_SCRIPT = r"""
(() => {
  try {
    Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32', configurable: true });
    Object.defineProperty(navigator, 'language', { get: () => 'zh-CN', configurable: true });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN'], configurable: true });
  } catch (e) {}
})();
"""


class XiaohongshuBrowser(BrowserPlatform):
    """小红书浏览器启动配置。"""

    @property
    def platform_id(self) -> str:
        return "xiaohongshu"

    def resolve_user_agent(self) -> str:
        configured = os.getenv("DINGDA_XIAOHONGSHU_LOGIN_USER_AGENT", "").strip()
        return configured or CHROME_DESKTOP_UA

    def resolve_proxy(self) -> dict[str, str] | None:
        server = os.getenv("DINGDA_XIAOHONGSHU_PROXY_SERVER", "").strip()
        username = os.getenv("DINGDA_XIAOHONGSHU_PROXY_USERNAME", "").strip()
        password = os.getenv("DINGDA_XIAOHONGSHU_PROXY_PASSWORD", "").strip()
        if not server:
            return None
        proxy: dict[str, str] = {"server": server}
        if username:
            proxy["username"] = username
        if password:
            proxy["password"] = password
        return proxy

    async def apply_anti_detect(self, context: Any, logger: logging.Logger) -> None:
        await inject_init_script(context, _ANTI_DETECT_SCRIPT, logger)


__all__ = ["XiaohongshuBrowser"]
