"""Camoufox 无头浏览器 — Dingda 全部浏览器自动化统一入口。"""

from __future__ import annotations

import contextlib
import logging
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
logger = logging.getLogger("dingda.camoufox")

# 淘系签名 cookie 走 .taobao.com，其余走 .goofish.com（对齐 goofish_cli）
_TAOBAO_COOKIE_NAMES = {
    "_m_h5_tk",
    "_m_h5_tk_enc",
    "x5sec",
    "sgcookie",
    "cookie2",
    "_tb_token_",
}

_XIANYU_HOME_URL = "https://www.goofish.com"
_XIANYU_AUTH_PROBE_URL = "https://www.goofish.com/bought"
_XIANYU_REQUIRED_COOKIES = ("_m_h5_tk", "unb", "cookie2")


def require_camoufox() -> None:
    try:
        import camoufox  # noqa: F401
    except ImportError as exc:
        raise ImportError("未安装 camoufox，请执行：uv sync") from exc


def cookie_domain(name: str) -> str:
    return ".taobao.com" if name in _TAOBAO_COOKIE_NAMES else ".goofish.com"


def cookies_to_playwright(cookies: dict[str, str]) -> list[dict[str, Any]]:
    """把 `{name: value}` 转成 Playwright `add_cookies` 列表。"""
    expires = int(time.time()) + 7 * 24 * 3600
    out: list[dict[str, Any]] = []
    for name, value in cookies.items():
        if not value:
            continue
        out.append(
            {
                "name": name,
                "value": value,
                "domain": cookie_domain(name),
                "path": "/",
                "expires": expires,
                "httpOnly": False,
                "secure": True,
                "sameSite": "None",
            }
        )
    return out


def playwright_cookie_map(raw_cookies: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(entry["name"]): str(entry["value"])
        for entry in raw_cookies
        if entry.get("name") and entry.get("value")
    }


@contextmanager
def headless_page(*, cookies: dict[str, str] | None = None) -> Iterator[Any]:
    """启动 Camoufox 无头页；可选注入 cookie 后 yield page。"""
    require_camoufox()
    from camoufox.sync_api import Camoufox

    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        if cookies:
            page.context.add_cookies(cookies_to_playwright(cookies))
        yield page


def _try_xianyu_quick_enter(page: Any) -> bool:
    """闲鱼首页 passport 弹窗点「快速进入」免密续期。"""
    iframe_el = page.query_selector("#alibaba-login-box")
    if not iframe_el:
        return True
    frame = iframe_el.content_frame()
    if not frame:
        logger.debug("alibaba-login-box iframe 未就绪")
        return False
    try:
        frame.wait_for_load_state("domcontentloaded", timeout=5_000)
        page.wait_for_timeout(800)
        frame.get_by_text("快速进入", exact=True).first.click(timeout=5_000)
        logger.info("Camoufox 已点击闲鱼「快速进入」")
        page.wait_for_selector("#alibaba-login-box", state="hidden", timeout=10_000)
        return True
    except Exception as exc:
        logger.warning("闲鱼「快速进入」不可用: %s", exc)
        return False


def refresh_xianyu_cookies(cookies: dict[str, str]) -> dict[str, str]:
    """用 Camoufox 访问闲鱼页面续期 cookie（对齐 goofish_cli refresh 流程）。"""
    with headless_page(cookies=cookies) as page:
        page.goto(_XIANYU_HOME_URL, wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_timeout(1500)
        if not _try_xianyu_quick_enter(page):
            return {}
        try:
            page.goto(_XIANYU_AUTH_PROBE_URL, wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_timeout(1500)
        except Exception as exc:
            logger.debug("Camoufox 访问 /bought 异常（忽略）: %s", exc)
        fresh = playwright_cookie_map(page.context.cookies())

    missing = [key for key in _XIANYU_REQUIRED_COOKIES if key not in fresh]
    if missing:
        logger.warning("Camoufox 续期后仍缺 cookie: %s", ", ".join(missing))
        return {}
    return fresh


async def launch_camoufox_renew_context(
    user_data_dir: Path,
    *,
    headless: bool = True,
) -> tuple[Any, Any]:
    """启动 Camoufox 续期会话（风控自动滑块用）。

    @returns (AsyncCamoufox 实例, BrowserContext)。调用方须 ``await cm.__aexit__`` 关闭。
    """
    require_camoufox()
    from camoufox.addons import DefaultAddons
    from camoufox.async_api import AsyncCamoufox

    fingerprint_os = (
        "windows"
        if sys.platform == "win32"
        else ("macos" if sys.platform == "darwin" else "linux")
    )
    user_data_dir.mkdir(parents=True, exist_ok=True)
    cm = AsyncCamoufox(
        headless=headless,
        humanize=False,
        persistent_context=True,
        user_data_dir=str(user_data_dir),
        locale="zh-CN",
        os=fingerprint_os,
        i_know_what_im_doing=True,
        exclude_addons=[DefaultAddons.UBO],
    )
    context = await cm.__aenter__()
    logger.info("Camoufox 续期会话已启动 headless=%s profile=%s", headless, user_data_dir)
    return cm, context


async def close_camoufox_renew_context(cm: Any) -> None:
    with contextlib.suppress(Exception):
        await cm.__aexit__(None, None, None)