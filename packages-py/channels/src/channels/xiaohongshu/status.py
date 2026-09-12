"""小红书登录态探活。

职责：
    用账号 cookie 打开探索页，按 xiaohongshu-mcp 的方式判断是否仍登录。

设计说明：
    - 对齐 ``CheckLoginStatus``：打开 ``/explore``，看侧栏 ``.main-container .user .link-wrapper .channel``
    - 走异步 BrowserManager / Pool，不占用扫码同步线程
    - 调用方：启动预热 ``probe_all_xiaohongshu``

使用示例：
    ok = await probe(cookie)
"""

from __future__ import annotations

import asyncio
import logging
import time

from browser.manager import get_browser_manager
from contracts.browser_port import LaunchOptions
from channels.cookie_header import parse_cookie_header
from channels.xiaohongshu.login import HOME_URL
from channels.xiaohongshu.cookies import COOKIE_DOMAIN, to_browser_cookies

logger = logging.getLogger("dingda.channel.xiaohongshu.status")

LOGIN_CHANNEL_SELECTOR = ".main-container .user .link-wrapper .channel"
_COUNT_JS = "(sel) => document.querySelectorAll(sel).length"


async def probe(cookie: str) -> bool:
    """打开探索页，侧栏有登录入口则视为未过期。"""
    cookies = parse_cookie_header(cookie)
    if not cookies.get("a1") or not cookies.get("web_session"):
        logger.info("小红书探活跳过：cookie 缺 a1/web_session")
        return False
    logger.info("小红书探活开始")
    manager = get_browser_manager()
    port = None
    page = None
    try:
        port = await manager.acquire(LaunchOptions(headless=True))
        page = await port.open(
            cookies=to_browser_cookies(cookies),
            default_domain=COOKIE_DOMAIN,
        )
        started = time.perf_counter()
        await page.goto(f"{HOME_URL}/explore", wait_until="domcontentloaded", timeout_ms=20_000)
        logger.info(
            "探活打开探索页 elapsed=%.2fs elapsed_ms=%d",
            time.perf_counter() - started,
            int((time.perf_counter() - started) * 1000),
        )
        # 侧栏登录入口是后渲染的，固定再等 1 秒
        wait_started = time.perf_counter()
        await asyncio.sleep(1.0)
        logger.info(
            "探活等待侧栏渲染 elapsed=%.2fs elapsed_ms=%d",
            time.perf_counter() - wait_started,
            int((time.perf_counter() - wait_started) * 1000),
        )
        count = int(await page.evaluate(_COUNT_JS, LOGIN_CHANNEL_SELECTOR) or 0)
        ok = count > 0
        logger.info("小红书探活完成 logged_in=%s selector_count=%s", ok, count)
        return ok
    except Exception as exc:
        logger.info("小红书探活失败: %s", exc)
        return False
    finally:
        if page is not None:
            await page.close()
        if port is not None:
            await manager.release(port)
