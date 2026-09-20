"""风控兜底：自动过不了时，开一个用户看得见的窗口让人手动过。

职责：
    提供 ``open_headed_browser`` —— 起一台**有头**浏览器打开目标页，把画面直播给
    前端，等用户手动过滑块 / 验证码，过了就回报成功。

设计说明：
    - 只在自动过风控失败后由主编排调用：自动过是无声的，人工过要占一台浏览器、
      还要打扰用户，不该默认走。
    - **判定「过没过」用启发式**（URL / 标题 / 正文里的风控关键词）：agent 包不
      import channels，拿不到平台那套风控判定，也不该拿 —— 人工过完长什么样由人判断，
      这里只负责把画面送过去、并在页面不再像风控页时收工。
    - 等待期间持续推帧：用户在前端看着画面操作，不用猜后端停在哪。
    - 超时按失败回报，不抛：主编排据此决定是重试还是如实告诉用户没过成。
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from agent.context import RunContext
from agent.loop import ToolSpec
from agent.session import crawl_session
from agent.steps import platform_label

logger = logging.getLogger("dingda.agent.tool.risk")

_WAIT_TIMEOUT_S = 180
_POLL_INTERVAL_S = 1.2
_CLEAR_HOLD_S = 5.0
_MIN_CONTENT_CHARS = 120
_BODY_JS = "() => (document.body && document.body.innerText || '')"

_BLOCKED_MARKS = (
    "punish",
    "captcha",
    "slider",
    "risk",
    "verify",
    "验证",
    "安全校验",
    "滑动",
)


@dataclass(frozen=True)
class _PageState:
    """一次人工窗口轮询到的判定输入。"""

    url: str
    title: str
    body: str
    shot: bytes


async def open_headed_browser(
    ctx: RunContext,
    platform: str,
    url: str | None = None,
    item_id: str | None = None,
) -> dict[str, Any]:
    """开一个有头窗口让用户手动过风控；阻塞到过完或超时（默认 180 秒）。"""
    plat = (platform or "").strip().lower()
    if not plat:
        return _fail("", "agent.invalid_input", "platform 不能为空")

    target = (url or "").strip()
    if not target and item_id:
        # 没给 URL 就按平台拼详情页，用户至少能落在对的地方
        from agent.tools.repair import _detail_url

        target = _detail_url(plat, item_id, None)
    if not target:
        return _fail(plat, "agent.invalid_input", "url 与 item_id 至少要给一个")

    await ctx.emit_text(
        f"自动过风控没成功。已打开一个{platform_label(plat)}窗口，"
        f"请手动完成验证（{int(_WAIT_TIMEOUT_S / 60)} 分钟内完成即可）。"
    )

    try:
        async with crawl_session(
            plat,
            ctx=ctx,
            cookie=ctx.cookie_for(plat),
            headless=False,
            dedicated=True,
        ) as session:
            page = await session.crawler.open_page(session.ctx())
            try:
                await page.goto(target)
                passed = await _wait_until_passed(ctx, page, plat)
            finally:
                await session.crawler.close_page(page)
    except Exception as exc:  # noqa: BLE001 — 工具层不抛，主编排靠 error_code 分流
        logger.exception("有头窗口异常 platform=%s", plat)
        return _fail(plat, "crawler.failed", str(exc))

    if not passed:
        return _fail(plat, "channel.risk", "等待超时，风控仍未解除")
    logger.info("人工过风控成功 platform=%s", plat)
    return {"ok": True, "platform": plat, "message": f"{platform_label(plat)}风控已解除，可以继续抓取"}


async def _wait_until_passed(ctx: RunContext, page: Any, platform: str) -> bool:
    """边推画面边等；风控 UI 消失且正文稳定渲染才算过。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _WAIT_TIMEOUT_S
    clear_since: float | None = None
    while True:
        state = await _page_state(page)
        if state is not None:
            await _push_frame(ctx, state)
            cleared = not _looks_blocked(state.url, state.title, state.body)
            cleared = cleared and len(state.body.strip()) >= _MIN_CONTENT_CHARS
            if cleared:
                if clear_since is None:
                    clear_since = loop.time()
                elif loop.time() - clear_since >= _CLEAR_HOLD_S:
                    return True
            else:
                clear_since = None
        if loop.time() >= deadline:
            return False
        await asyncio.sleep(_POLL_INTERVAL_S)


async def _page_state(page: Any) -> _PageState | None:
    """读取截图、地址、标题和正文；读不到就返回 None。"""
    try:
        shot = await page.screenshot()
        url = str(getattr(page, "url", "") or "")
        title = str(getattr(page, "title", "") or "")
    except Exception:  # noqa: BLE001 — 截图失败不影响判定，继续等下一跳
        logger.debug("有头窗口截图失败", exc_info=True)
        return False
    try:
        body = str(await page.evaluate(_BODY_JS) or "")
    except Exception:  # noqa: BLE001 — 页面跳转瞬间可能取不到正文
        body = ""
    return _PageState(url=url, title=title, body=body, shot=shot if isinstance(shot, bytes) else b"")


async def _push_frame(ctx: RunContext, state: _PageState) -> None:
    """把人工窗口画面推给前端。"""
    await ctx.emit_frame(
        url=state.url,
        title=state.title,
        hint="请手动完成验证",
        mime="image/jpeg",
        image_b64=base64.b64encode(state.shot).decode("ascii"),
    )


def _looks_blocked(url: str, title: str, body: str) -> bool:
    """判定是否仍像风控页；正文足够长后，旧 URL 关键词不再单独拦住通过。"""
    if any(mark.lower() in body.lower() for mark in _BLOCKED_MARKS):
        return True
    if len(body.strip()) >= _MIN_CONTENT_CHARS:
        return False
    haystack = f"{url} {title}".lower()
    return any(mark.lower() in haystack for mark in _BLOCKED_MARKS)


def _fail(platform: str, code: str, message: str) -> dict[str, Any]:
    """失败出参。"""
    return {
        "ok": False,
        "platform": platform or "unknown",
        "error_code": code,
        "message": f"{platform_label(platform)}：{message}".lstrip("："),
    }


class HeadedInput(BaseModel):
    """开有头窗口的入参。"""

    platform: str = Field(description="平台：xianyu / xiaohongshu / ali1688")
    url: str | None = Field(default=None, description="要打开的页面；不给就用 item_id 拼详情页")
    item_id: str | None = Field(default=None, description="商品或笔记 id，用于拼详情页")


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="open_headed_browser",
        label="人工过风控 · {platform}",
        description=(
            "自动过风控失败后的兜底：开一个用户看得见的浏览器窗口，把画面直播给用户，"
            "等用户手动完成滑块 / 验证码。**先一句话告诉用户要做什么**再调。"
            "最多等 3 分钟；超时会返回 channel.risk。"
        ),
        args=HeadedInput,
        fn=open_headed_browser,
        browser=True,
    ),
)
