"""平台浏览器抽象：UA、代理、反检测由各平台子类实现。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any


class BrowserPlatform(ABC):
    """Playwright 启动时的平台差异入口。"""

    @property
    @abstractmethod
    def platform_id(self) -> str:
        """平台标识，如 ``xianyu`` / ``ali1688``。"""

    @abstractmethod
    def resolve_user_agent(self) -> str:
        """登录/续期用的 User-Agent。"""

    @abstractmethod
    def resolve_proxy(self) -> dict[str, str] | None:
        """Playwright 代理配置；无代理则 ``None``。"""

    @abstractmethod
    async def apply_anti_detect(self, context: Any, logger: logging.Logger) -> None:
        """向浏览器上下文注入平台反检测脚本。"""
