"""小红书风控恢复：有头窗口阻塞等人。

职责：
    实现 RiskRecoverPort。小红书暂无稳定自动滑块，直接弹有头窗口，
    阻塞直到用户过验证，并把窗口里拿到的 Cookie 写回原 page。

设计说明：
    - 与闲鱼第二级人工等待对称；日后有自动解法再填第一级
    - 判定用正向证据（验证 UI 消失 + 正文渲染 + 稳定保持），
      只看"没看到验证页"会在刚 goto 还没渲染时误判为通过
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import Any

from browser.manager import BrowserManager
from contracts.browser_port import Cookie, LaunchOptions, Page
from core.errors import AppError, risk_control_error

logger = logging.getLogger("dingda.channel.xiaohongshu.risk_recovery")

_MANUAL_TIMEOUT_S = float(os.getenv("DINGDA_MANUAL_SLIDER_TIMEOUT_S", "180") or "180")
_MANUAL_POLL_S = 1.2
# 验证 UI 消失后还要稳定保持这么久，才认定人工真的过了；
# 保持窗口要长于"正文先渲染、验证页随后弹出"的延迟，否则会在弹窗前判过
_MANUAL_CLEAR_HOLD_S = 5.0
# 目标正文至少要渲出这么多字符；验证页未渲染 / 空白页都到不了这个量
_MANUAL_MIN_CONTENT_CHARS = 120
_RISK_TEXT = ("安全验证", "请完成验证", "拖动下方滑块")
_URL_TOKENS = ("captcha", "punish")
_BODY_JS = "() => (document.body && document.body.innerText || '')"


class XiaohongshuRiskRecovery:
    """小红书风控恢复插头（人工有头等待）。"""

    platform = "xiaohongshu"

    async def recover_risk(
        self,
        page: Page,
        *,
        where: str,
        url: str | None = None,
    ) -> None:
        """有头窗口等人过验证，并把新 Cookie 写回原 page。"""
        target = (url or getattr(page, "url", "") or "").strip() or "https://www.xiaohongshu.com/"
        cookies = await _cookies_from_page(page)
        fresh = await _wait_manual_headed(
            target,
            cookies=cookies,
            where=where,
            timeout_s=_MANUAL_TIMEOUT_S,
        )
        await _write_back_cookies(page, fresh, where=where)


async def _cookies_from_page(page: Page) -> list[Cookie]:
    try:
        return list(await page.cookies())
    except Exception:  # noqa: BLE001
        return []


async def _write_back_cookies(page: Page, fresh: list[Cookie], *, where: str) -> None:
    """把人工窗口里拿到的 Cookie 写回原 page，否则调用方重试仍会撞验证页。"""
    if not fresh:
        return
    try:
        await page.add_cookies(fresh)
        logger.info("xhs manual cookies written back where=%s count=%s", where, len(fresh))
    except Exception:  # noqa: BLE001
        logger.warning("小红书 Cookie 回写失败，重试可能仍撞风控 where=%s", where, exc_info=True)


async def _body_text(page: Page) -> str:
    try:
        return str(await page.evaluate(_BODY_JS) or "")
    except Exception:  # noqa: BLE001
        return ""


async def _raw_is_blocked(raw: Any) -> bool:
    """遍历主文档与子 frame：验证页也可能挂在 iframe 里。"""
    scopes: list[Any] = [raw]
    with contextlib.suppress(Exception):
        scopes.extend(raw.frames)
    for scope in scopes:
        url = str(getattr(scope, "url", "") or "").lower()
        if any(token in url for token in _URL_TOKENS):
            return True
        try:
            blob = str(
                await scope.evaluate(
                    "() => (document.body && document.body.innerText || '').slice(0, 2000)"
                )
                or ""
            )
        except Exception:  # noqa: BLE001
            continue
        if any(hint in blob for hint in _RISK_TEXT):
            return True
    return False


async def _wait_manual_headed(
    url: str,
    *,
    cookies: list[Cookie],
    where: str,
    timeout_s: float,
) -> list[Cookie]:
    """有头窗口阻塞到用户过验证；返回窗口里的最新 Cookie。

    判定要求验证 UI 消失、正文渲染出来、且稳定保持 ``_MANUAL_CLEAR_HOLD_S``。
    """
    manager = BrowserManager(max_browsers=1, max_contexts_per_browser=1)
    port = None
    headed: Page | None = None
    try:
        port = await manager.acquire(LaunchOptions(headless=False))
        headed = await port.open(
            cookies=cookies or None,
            default_domain=".xiaohongshu.com",
        )
        logger.info("xhs manual risk window open where=%s url=%s", where, url[:120])
        await headed.goto(url, wait_until="domcontentloaded", timeout_ms=45_000)

        raw = getattr(headed, "raw", None)
        deadline = time.monotonic() + max(30.0, timeout_s)
        clear_since: float | None = None
        blocked = False
        while time.monotonic() < deadline:
            if raw is not None and await _raw_is_blocked(raw):
                if not blocked:
                    blocked = True
                    logger.info(
                        "xhs manual risk waiting operator where=%s url=%s",
                        where,
                        (headed.url or "")[:120],
                    )
                clear_since = None
            elif len((await _body_text(headed)).strip()) >= _MANUAL_MIN_CONTENT_CHARS:
                if clear_since is None:
                    clear_since = time.monotonic()
                elif time.monotonic() - clear_since >= _MANUAL_CLEAR_HOLD_S:
                    logger.info(
                        "xhs manual risk passed where=%s had_block=%s url=%s",
                        where,
                        blocked,
                        (headed.url or "")[:120],
                    )
                    return await _cookies_from_page(headed)
            else:
                clear_since = None
            await asyncio.sleep(_MANUAL_POLL_S)

        raise risk_control_error(f"{where} 人工验证超时（{int(timeout_s)}s）")
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("xhs manual risk failed where=%s", where)
        raise risk_control_error(f"{where} 人工验证失败：{exc}") from exc
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
