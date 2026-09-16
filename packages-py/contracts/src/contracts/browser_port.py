"""浏览器插座：Crawler / Channel / Tool 只依赖本接口，不碰 Playwright/Camoufox。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
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


class PageEvent(StrEnum):
    """页面生命周期事件（平台无关）。

    设计说明：
        命名按「浏览器生命周期」而非某引擎的事件名，站点差异一律由调用方
        自己用选择器 / URL 片段 / JS 判据表达。有了这层，调用方不必再靠
        固定 sleep 猜页面进度。
    """

    NAVIGATION_START = "navigation_start"
    DOM_READY = "dom_ready"
    LOADED = "loaded"
    REQUEST = "request"
    RESPONSE = "response"
    REQUEST_DONE = "request_done"
    REQUEST_FAILED = "request_failed"
    PAGE_ERROR = "page_error"
    CLOSED = "closed"


@dataclass(frozen=True)
class PageEventInfo:
    """归一化后的事件负载，不含任何引擎对象。"""

    event: PageEvent
    url: str = ""
    method: str = ""
    status: int = 0
    resource_type: str = ""
    error: str = ""
    message: str = ""


PageEventHandler = Callable[[PageEventInfo], Any]


class Page(ABC):
    """单页插座：导航、交互、Cookie、截图。"""

    @property
    @abstractmethod
    def url(self) -> str:
        """当前页 URL。"""

    @abstractmethod
    def on(self, event: PageEvent, handler: PageEventHandler) -> Callable[[], None]:
        """订阅页面事件；返回取消订阅函数。

        导航类事件（NAVIGATION_START / DOM_READY / LOADED）必须在 ``goto``
        **之前**注册，否则会错过——这是「不靠 sleep 等加载」的前提。
        处理器在事件循环里同步调用，抛异常只记日志、不影响页面。
        """

    @abstractmethod
    async def wait_for_event(
        self,
        event: PageEvent,
        *,
        url_contains: str = "",
        timeout_ms: int = 15_000,
    ) -> PageEventInfo | None:
        """等首个匹配事件；超时返回 None（不抛）。

        ``url_contains`` 只在网络类事件上有意义，用于过滤到某个接口。
        注意监听从调用时才开始，已发生的事件不会补发。
        """

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
    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: str = "visible",
        timeout_ms: int = 15_000,
    ) -> bool:
        """等选择器达到 state（visible/attached/hidden/detached）；超时返回 False。

        设计说明：
            一律不抛超时异常——风控页永远等不到正常元素，抛异常会打断
            ``_blocked`` 之类的风控分支，把「被拦」误报成「抽取失败」。
        """

    @abstractmethod
    async def wait_for_load_state(
        self,
        state: str = "domcontentloaded",
        *,
        timeout_ms: int = 30_000,
    ) -> bool:
        """等页面加载状态（domcontentloaded/load/networkidle）；超时返回 False。"""

    @abstractmethod
    async def wait_for_function(
        self,
        expression: str,
        arg: Any = None,
        *,
        timeout_ms: int = 15_000,
    ) -> bool:
        """轮询 JS 表达式直到返回真值；超时返回 False。

        用于「等页面自渲染出内容」这类没有稳定选择器、只有复合判据的场景。
        """

    @abstractmethod
    async def wait_for_response(
        self,
        url_contains: str,
        *,
        timeout_ms: int = 15_000,
    ) -> Any | None:
        """等首个 URL 含 ``url_contains`` 的响应；超时返回 None。

        返回值是引擎原始响应对象，仅供取 status / json，不得向下游传递。
        """

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
    async def screenshot(
        self,
        path: Path | None = None,
        *,
        image_type: str = "png",
        quality: int | None = None,
    ) -> bytes:
        """截图；可选落盘。image_type=png|jpeg；jpeg 可传 quality(0-100)。"""

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
