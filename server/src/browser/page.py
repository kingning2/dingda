"""Playwright 兼容 Page 包装：Camoufox / Playwright adapter 共用。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode, urlparse, urlunparse

from src.browser.context import cookies_to_playwright, normalize_cookies
from src.browser.port import Cookie, Page

logger = logging.getLogger("dingda.browser.page")


class PlaywrightPage(Page):
    """把 Playwright/Camoufox 的 page 包成 BrowserPort 用的 Page。"""

    def __init__(
        self,
        page: Any,
        *,
        context: Any | None = None,
        owns_context: bool = False,
    ) -> None:
        self._page = page
        self._context = context if context is not None else page.context
        self._owns_context = owns_context
        self._closed = False

    @property
    def raw(self) -> Any:
        """底层 Playwright page（仅 adapter / 交互原语使用，业务禁止依赖）。"""
        return self._page

    @property
    def context(self) -> Any:
        """底层 BrowserContext（Cookie / Channel 交互原语用）。"""
        return self._context

    @property
    def url(self) -> str:
        return str(self._page.url or "")

    async def goto(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        wait_until: str = "domcontentloaded",
        timeout_ms: int = 30_000,
    ) -> None:
        """打开 URL。"""
        target = _with_query(url, params)
        logger.info("页面跳转 url=%s", target)
        await self._page.goto(target, wait_until=wait_until, timeout=timeout_ms)

    async def content(self) -> str:
        """返回 HTML。"""
        return await self._page.content()

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        """在页面执行 JS。"""
        if arg is None:
            return await self._page.evaluate(expression)
        return await self._page.evaluate(expression, arg)

    async def click(self, selector: str, *, timeout_ms: int = 10_000) -> None:
        """点击。"""
        logger.info("页面点击 selector=%s", selector)
        await self._page.click(selector, timeout=timeout_ms)

    async def fill(self, selector: str, value: str, *, timeout_ms: int = 10_000) -> None:
        """填表。"""
        logger.info("页面填表 selector=%s", selector)
        await self._page.fill(selector, value, timeout=timeout_ms)

    async def screenshot(
        self,
        path: Path | None = None,
        *,
        image_type: str = "png",
        quality: int | None = None,
    ) -> bytes:
        """截图（png / jpeg）。"""
        kind = (image_type or "png").strip().lower()
        if kind not in {"png", "jpeg"}:
            kind = "png"
        kwargs: dict[str, Any] = {"type": kind}
        if kind == "jpeg":
            kwargs["quality"] = int(quality) if quality is not None else 60
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            kwargs["path"] = str(path)
        data = await self._page.screenshot(**kwargs)
        return bytes(data)

    async def cookies(self) -> list[Cookie]:
        """导出 Cookie。"""
        raw = await self._context.cookies()
        return [
            Cookie(
                name=str(item.get("name") or ""),
                value=str(item.get("value") or ""),
                domain=str(item.get("domain") or ""),
                path=str(item.get("path") or "/"),
                expires=item.get("expires"),
                http_only=bool(item.get("httpOnly", False)),
                secure=bool(item.get("secure", False)),
                same_site=str(item.get("sameSite") or "Lax"),
            )
            for item in raw
            if item.get("name") and item.get("value")
        ]

    async def add_cookies(
        self,
        cookies: Sequence[Cookie] | Mapping[str, str],
        *,
        default_domain: str = "",
    ) -> None:
        """注入 Cookie。"""
        normalized = normalize_cookies(cookies, default_domain=default_domain)
        payload = cookies_to_playwright(normalized)
        if not payload:
            return
        await self._context.add_cookies(payload)
        logger.info("页面已注入 Cookie count=%s", len(payload))

    async def close(self) -> None:
        """关闭页；若独占 context 则一并关闭。"""
        if self._closed:
            return
        self._closed = True
        logger.info("关闭页面 url=%s", self.url)
        try:
            await self._page.close()
        finally:
            if self._owns_context and self._context is not None:
                await self._context.close()


def _with_query(url: str, params: Mapping[str, str] | None) -> str:
    if not params:
        return url
    parsed = urlparse(url)
    query = urlencode(dict(params))
    if parsed.query:
        query = f"{parsed.query}&{query}"
    return urlunparse(parsed._replace(query=query))
