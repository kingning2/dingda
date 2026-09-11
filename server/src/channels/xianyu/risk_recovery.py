"""闲鱼风控恢复：自动滑块 → 有头窗口阻塞等人。

职责：
    实现爬虫步骤级 RiskRecoverPort：先 try_solve_slider；
    失败则另开有头 Camoufox，阻塞等到用户手过或超时，并把窗口里拿到的新
    Cookie 写回原 page（不回写的话调用方重试仍会撞同一张 punish 页）。

设计说明：
    - 平台特例留在本包；不进 Browser adapter
    - 人工等待要求正向证据：风控 UI 消失 + 目标正文真的渲染 + 稳定保持。
      只用"没看到滑块就算过"会在 goto 后页面还没渲染时误判，等于没等人
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from src.browser.manager import BrowserManager
from src.browser.port import Cookie, LaunchOptions, Page
from src.channels.xianyu.slider import (
    auto_slider_enabled,
    clear_risk_cookies,
    page_is_risk_block,
    try_solve_slider,
)
from src.shared.errors import AppError, risk_control_error

logger = logging.getLogger("dingda.channel.xianyu.risk_recovery")

_MANUAL_TIMEOUT_S = float(os.getenv("DINGDA_MANUAL_SLIDER_TIMEOUT_S", "180") or "180")
_MANUAL_POLL_S = 1.2
# 风控 UI 消失后还要稳定保持这么久，才认定人工真的过了。
# 取 5s 是因为 punish 页常在正文渲染后 3s 左右才弹出来（见 risk recovery 日志），
# 保持窗口短于这个延迟就会在弹窗前判过。
_MANUAL_CLEAR_HOLD_S = 5.0
# 目标正文至少要渲出这么多字符；风控页未渲染 / 空白页都到不了这个量
_MANUAL_MIN_CONTENT_CHARS = 120
_BODY_JS = "() => (document.body && document.body.innerText || '')"


class XianyuRiskRecovery:
    """闲鱼风控恢复插头。"""

    platform = "xianyu"

    async def recover_risk(
        self,
        page: Page,
        *,
        where: str,
        url: str | None = None,
    ) -> None:
        """自动滑块；失败则有头窗口等人，并把新 Cookie 写回原 page。"""
        target = (url or getattr(page, "url", "") or "").strip()
        logger.info("risk recover start where=%s url=%s", where, target[:120])

        raw = getattr(page, "raw", None)
        context = getattr(page, "context", None)
        if auto_slider_enabled() and raw is not None and context is not None:
            await clear_risk_cookies(context)
            ok, detail = await try_solve_slider(
                raw,
                context,
                max_retries=3,
                prefer_page_mouse=True,
            )
            logger.info("risk auto slider where=%s ok=%s detail=%s", where, ok, detail)
            if ok:
                return

        cookies = await _cookies_from_page(page)
        fresh = await _wait_manual_headed(
            target or "https://www.goofish.com/",
            cookies=cookies,
            where=where,
            timeout_s=_MANUAL_TIMEOUT_S,
        )
        await _write_back_cookies(page, fresh, where=where)


async def _cookies_from_page(page: Page) -> list[Cookie]:
    try:
        return list(await page.cookies())
    except Exception:  # noqa: BLE001
        logger.debug("export cookies failed", exc_info=True)
        return []


async def _write_back_cookies(page: Page, fresh: list[Cookie], *, where: str) -> None:
    """把人工窗口里拿到的 Cookie 写回原 page。

    人工过滑块换来的凭证只存在于那个有头 context；不回写的话调用方拿原
    context 重试，仍然会撞同一张 punish 页 —— 等于白等一场。
    """
    if not fresh:
        return
    try:
        await page.add_cookies(fresh)
        logger.info("manual slider cookies written back where=%s count=%s", where, len(fresh))
    except Exception:  # noqa: BLE001
        logger.warning("人工滑块 Cookie 回写失败，重试可能仍撞风控 where=%s", where, exc_info=True)


async def _body_text(page: Page) -> str:
    try:
        return str(await page.evaluate(_BODY_JS) or "")
    except Exception:  # noqa: BLE001
        return ""


async def _content_rendered(page: Page) -> bool:
    """目标正文是否真的渲出来了。"""
    return len((await _body_text(page)).strip()) >= _MANUAL_MIN_CONTENT_CHARS


async def _wait_manual_headed(
    url: str,
    *,
    cookies: list[Cookie],
    where: str,
    timeout_s: float,
) -> list[Cookie]:
    """有头浏览器打开风控页，阻塞直到用户通过；返回窗口里的最新 Cookie。

    判定用正向证据：风控 UI 消失、正文渲染出来、且稳定保持 ``_MANUAL_CLEAR_HOLD_S``。
    单看"没看到滑块"会在页面刚 goto 还没渲染时立即为真，那等于没等人。
    """
    manager = BrowserManager(max_browsers=1, max_contexts_per_browser=1)
    port = None
    headed: Page | None = None
    try:
        port = await manager.acquire(LaunchOptions(headless=False))
        headed = await port.open(
            cookies=cookies or None,
            default_domain=".goofish.com",
        )
        logger.info("manual slider window open where=%s url=%s", where, url[:120])
        await headed.goto(url, wait_until="domcontentloaded", timeout_ms=45_000)

        raw = getattr(headed, "raw", None)
        deadline = time.monotonic() + max(30.0, timeout_s)
        clear_since: float | None = None
        blocked = False
        while time.monotonic() < deadline:
            if raw is not None and await page_is_risk_block(raw):
                if not blocked:
                    blocked = True
                    logger.info(
                        "manual slider waiting operator where=%s url=%s",
                        where,
                        (headed.url or "")[:120],
                    )
                clear_since = None
            elif await _content_rendered(headed):
                if clear_since is None:
                    clear_since = time.monotonic()
                elif time.monotonic() - clear_since >= _MANUAL_CLEAR_HOLD_S:
                    logger.info(
                        "manual slider passed where=%s had_block=%s url=%s",
                        where,
                        blocked,
                        (headed.url or "")[:120],
                    )
                    return await _cookies_from_page(headed)
            else:
                clear_since = None
            await asyncio.sleep(_MANUAL_POLL_S)

        raise risk_control_error(f"{where} 人工滑块超时（{int(timeout_s)}s）")
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("manual slider failed where=%s", where)
        raise risk_control_error(f"{where} 人工滑块失败：{exc}") from exc
    finally:
        if headed is not None:
            try:
                await headed.close()
            except Exception:  # noqa: BLE001
                pass
        if port is not None:
            try:
                await manager.release(port)
            except Exception:  # noqa: BLE001
                pass
        try:
            await manager.stop()
        except Exception:  # noqa: BLE001
            pass
