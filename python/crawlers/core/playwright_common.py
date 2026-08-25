"""Playwright 公用能力：浏览器启动、stealth、通用页面操作。

平台相关的 UA / 代理 / 反检测由 `crawlers.<platform>.browser.BrowserPlatform` 子类实现，
经 [`create_channel`] 获取渠道实例后调用 ``channel.browser()``。
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

try:  # playwright 为可选运行时依赖；缺失或损坏时降级。
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright
except Exception:  # pragma: no cover — ImportError / 损坏扩展（如 greenlet）
    async_playwright = None  # type: ignore[assignment]
    Browser = Any  # type: ignore[assignment,misc]
    BrowserContext = Any  # type: ignore[assignment,misc]
    Page = Any  # type: ignore[assignment,misc]

try:  # playwright-stealth 为可选运行时依赖；缺失时沿用基础参数。
    from playwright_stealth import Stealth
except Exception:  # pragma: no cover — ImportError / 包损坏
    Stealth = None  # type: ignore[assignment]

logger = logging.getLogger("dingda.sidecar.playwright")

# 系统浏览器优先（避免下载 Playwright Chromium；真实 Edge/Chrome 指纹更抗风控）。
SYSTEM_CHANNELS = ("msedge", "chrome")

CHROME_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_VIEWPORT = {"width": 1280, "height": 800}
LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-popup-blocking",
]


def to_serializable_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 Playwright cookie 对象转换为可序列化结构。"""
    return [
        {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", ""),
            "expires": c.get("expires"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": c.get("sameSite") or "Lax",
        }
        for c in cookies
        if c.get("name") and c.get("value")
    ]


async def apply_stealth(context: BrowserContext, logger: Any) -> None:
    """对 Playwright context 注入 stealth 补丁。"""
    if Stealth is None:
        logger.warning("playwright-stealth 未安装，沿用基础反检测参数")
        return
    await Stealth(init_scripts_only=True).apply_stealth_async(context)


async def inject_init_script(context: BrowserContext, script: str, logger: Any) -> None:
    """向 context 注入 init script。"""
    try:
        await context.add_init_script(script)
    except Exception:  # noqa: BLE001
        logger.warning("注入 init script 失败（不影响主流程）")


def clear_profile_locks(user_data_dir: Path) -> None:
    """清理上次未干净退出留下的 Chromium 锁文件。"""
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        lock = user_data_dir / name
        with contextlib.suppress(OSError):
            if lock.exists():
                lock.unlink()


async def launch_persistent_chromium(
    playwright: Any,
    user_data_dir: str | Path,
    **kwargs: Any,
) -> BrowserContext:
    """用系统浏览器（Edge/Chrome）启动持久化上下文；都不可用则退回自带 Chromium。

    避免为登录/续期下载 Playwright Chromium；真实 Edge/Chrome 指纹更抗风控。
    """
    clear_profile_locks(Path(user_data_dir))
    last_error: str | None = None
    for channel in SYSTEM_CHANNELS + (None,):
        opts = dict(kwargs)
        if channel:
            opts["channel"] = channel
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(user_data_dir), **opts
            )
            logger.info("浏览器已启动 channel=%s", channel or "bundled")
            return context
        except Exception as error:  # noqa: BLE001
            last_error = str(error)
            logger.warning("浏览器启动失败 channel=%s: %s", channel, str(error)[:120])
    raise RuntimeError(f"启动浏览器失败（已尝试 Edge/Chrome/自带）: {last_error}")


async def try_click_first(page: Page, selectors: list[str]) -> bool:
    """依次尝试点击首个可见元素。"""
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            if await locator.is_visible():
                await locator.click(timeout=2000)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def fill_first(page: Page, selectors: list[str], value: str) -> bool:
    """依次尝试填充首个可见输入框。"""
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            if await locator.is_visible():
                await locator.fill(value, timeout=3000)
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def extract_first_text(page: Page, selectors: list[str]) -> str | None:
    """读取首个可见错误文案。"""
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            if await locator.is_visible():
                text = (await locator.inner_text(timeout=1000)).strip()
                if text:
                    return text
        except Exception:  # noqa: BLE001
            continue
    return None


class BrowserSession:
    """临时浏览器会话封装，统一回收 context 与 browser。"""

    def __init__(self) -> None:
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            if self.context:
                await self.context.close()
        with contextlib.suppress(Exception):
            if self.browser:
                await self.browser.close()
        self.browser = None
        self.context = None
        self.page = None
