"""浏览器插座：Crawler / Channel / Tool 只依赖本接口，不碰 Playwright/Camoufox。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Mapping, Sequence


@dataclass(frozen=True)
class Cookie:
    """通用 Cookie，不含任何平台域名特例。"""

    name: str
    value: str
    domain: str = ""
    path: str = "/"
    expires: float | None = None
    http_only: bool = False
    secure: bool = True
    same_site: str = "Lax"


@dataclass(frozen=True)
class LaunchOptions:
    """引擎启动参数；缺省走各 adapter 默认配置。"""

    headless: bool = True
    proxy_url: str | None = None
    fingerprint_profile: str | None = None
    user_data_dir: Path | None = None
    locale: str = "zh-CN"
    extra: dict[str, Any] = field(default_factory=dict)


class Page(ABC):
    """单页插座：导航、交互、Cookie、截图。"""

    @property
    @abstractmethod
    def url(self) -> str:
        """当前页 URL。"""

    @abstractmethod
    async def goto(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        wait_until: str = "domcontentloaded",
        timeout_ms: int = 30_000,
    ) -> None:
        """打开 URL；params 会拼到 query。"""

    @abstractmethod
    async def content(self) -> str:
        """返回页面 HTML。"""

    @abstractmethod
    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        """在页面执行 JS；expression 为函数或表达式字符串。"""

    @abstractmethod
    async def click(self, selector: str, *, timeout_ms: int = 10_000) -> None:
        """点击选择器。"""

    @abstractmethod
    async def fill(self, selector: str, value: str, *, timeout_ms: int = 10_000) -> None:
        """填充输入框。"""

    @abstractmethod
    async def screenshot(self, path: Path | None = None) -> bytes:
        """截图；可选落盘，始终返回 PNG bytes。"""

    @abstractmethod
    async def cookies(self) -> list[Cookie]:
        """导出当前 context 的 Cookie。"""

    @abstractmethod
    async def add_cookies(
        self,
        cookies: Sequence[Cookie] | Mapping[str, str],
        *,
        default_domain: str = "",
    ) -> None:
        """注入 Cookie；dict 形式必须带 default_domain。"""

    @abstractmethod
    async def close(self) -> None:
        """关闭本页（及本页独占的 context，若有）。"""


class BrowserPort(ABC):
    """浏览器引擎插座：launch → open page → close。"""

    engine: ClassVar[str]

    @abstractmethod
    async def launch(self, options: LaunchOptions | None = None) -> None:
        """启动引擎（可重复调用，已启动则忽略）。"""

    @abstractmethod
    async def open(
        self,
        *,
        proxy: str | None = None,
        fingerprint: str | None = None,
        cookies: Sequence[Cookie] | Mapping[str, str] | None = None,
        default_domain: str = "",
    ) -> Page:
        """按代理/指纹/Cookie 打开一页，供 Crawler 基类调用。"""

    @abstractmethod
    async def close(self) -> None:
        """关闭引擎与全部残留页。"""
