"""1688 Playwright 浏览器配置。

``Ali1688Browser`` 继承平台浏览器抽象，提供 UA / 反检测等 1688 专用参数。"""

from __future__ import annotations

import os

from dingda_sidecar.crawlers.core.playwright_common import CHROME_DESKTOP_UA
from dingda_sidecar.crawlers.goofish.browser import XianyuBrowser


class Ali1688Browser(XianyuBrowser):
    """1688 浏览器配置；反检测与闲鱼共用 Baxia 栈。"""

    @property
    def platform_id(self) -> str:
        return "ali1688"

    def resolve_user_agent(self) -> str:
        configured = os.getenv("DINGDA_ALI1688_LOGIN_USER_AGENT", "").strip()
        return configured or CHROME_DESKTOP_UA

    def resolve_proxy(self) -> dict[str, str] | None:
        server = os.getenv("DINGDA_ALI1688_PROXY_SERVER", "").strip()
        username = os.getenv("DINGDA_ALI1688_PROXY_USERNAME", "").strip()
        password = os.getenv("DINGDA_ALI1688_PROXY_PASSWORD", "").strip()
        if not server:
            return None
        proxy: dict[str, str] = {"server": server}
        if username:
            proxy["username"] = username
        if password:
            proxy["password"] = password
        return proxy
