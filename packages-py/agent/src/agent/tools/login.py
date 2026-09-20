"""扫码登录：起一次扫码会话，把二维码推给用户，阻塞到扫完。

职责：
    提供 ``login`` 工具与 ``login_blocking`` 底层实现：驱动 ``RunContext.login_port``
    （接线方注入，实现走 ``domains.channel.qr_service``）完成一次扫码登录，
    把二维码推成 ``login`` 步骤帧，轮询到成功或超时为止。

设计说明：
    - **不 import ``channels`` / ``infrastructure``**（agent 包的禁止依赖）：登录在同步
      浏览器线程上跑，这里只通过 ``LoginPort`` 三个方法说话，用 ``asyncio.to_thread``
      包起来不堵事件循环。
    - **cookie 落库不在本模块**：``LoginPort.check`` 在状态到 ``success`` 时自己落库。
      这里只回传 ``account_id`` / ``display_name``，不认识账号库。
    - 二维码走 ``ctx.emit_frame``（``data:`` URL），步骤块 ``kind=login``，前端挂扫码块
      —— 不用浏览器直播页卡样式。
    - ``login_port`` 没接时返回 ``agent.login_unavailable``：与「接线方没接」的其它表达
      一致，不假装能登。
"""

from __future__ import annotations

import asyncio
import logging

from contracts.channel import QrStartRequest
from pydantic import BaseModel, Field

from agent.context import RunContext
from agent.loop import ToolSpec
from agent.steps import platform_label

logger = logging.getLogger("dingda.agent.tool.login")

# 状态字面量与 channels.types.LoginStatus 同源，故意不 import channels。
_STATUS_SUCCESS = "success"
_STATUS_FAILED = "failed"
_STATUS_EXPIRED = "expired"

# 各平台扫码窗口（秒）。
_PLATFORM_TIMEOUT = {"xianyu": 120, "xiaohongshu": 240, "ali1688": 180}
_POLL_INTERVAL_S = 1.5


async def login(ctx: RunContext, platform: str) -> dict[str, object]:
    """让用户扫码登录一个平台；阻塞到扫完或超时。"""
    return await login_blocking(platform, ctx)


async def login_blocking(
    platform: str,
    ctx: RunContext,
    *,
    step_id: str | None = None,
    hint: str | None = None,
) -> dict[str, object]:
    """起扫码会话 → 推二维码 → 轮询到成功 / 失败 / 超时。**一路阻塞到用户扫完**。

    ``step_id`` 把二维码帧钉到指定登录块上（掉线恢复时必须填，否则被还在跑的抓取块
    抢走）；``hint`` 是卡片角标文案，默认「用 App 扫码登录」。
    失败用返回值表达，不抛 —— 与其它工具同一条约定。
    """
    plat = (platform or "").strip().lower()
    timeout = _PLATFORM_TIMEOUT.get(plat)
    if timeout is None:
        return _fail(plat, "login.platform_unsupported", f"{plat or '该平台'} 不支持扫码登录")

    port = ctx.login_port
    if port is None:
        return _fail(plat, "agent.login_unavailable", "当前运行环境没有接扫码登录口子")

    started = await asyncio.to_thread(port.start, QrStartRequest(platform=plat))
    session_id = started.session_id
    if not started.ok or not session_id:
        logger.warning("扫码启动失败 platform=%s status=%s", plat, started.status)
        return {
            "ok": False,
            "platform": plat,
            "status": str(started.status or ""),
            "error_code": "login.failed",
            "message": started.detail or "无法启动扫码登录",
        }

    logger.info("扫码会话已开 platform=%s session=%s", plat, session_id)
    await _push_qr(ctx, plat, started.qr_base64, step_id=step_id, hint=hint)

    try:
        return await _poll(port, plat, session_id, timeout)
    except Exception:
        # 让后台扫码任务立刻让出同步浏览器，别把下一位用户堵住
        logger.exception("扫码轮询异常，取消会话 platform=%s session=%s", plat, session_id)
        await asyncio.to_thread(port.cancel, session_id)
        raise


async def _poll(port: object, platform: str, session_id: str, timeout: int) -> dict[str, object]:
    """按 1.5s 一跳轮询；成功带账号回，失败 / 超时如实报。"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        if loop.time() >= deadline:
            await asyncio.to_thread(port.cancel, session_id)
            logger.info("扫码超时 platform=%s session=%s", platform, session_id)
            return {
                "ok": False,
                "platform": platform,
                "status": _STATUS_EXPIRED,
                "error_code": "login.timeout",
                "message": f"{platform_label(platform)}扫码超时（{timeout} 秒），可以让用户重试",
            }

        snapshot = await asyncio.to_thread(port.check, session_id)
        status = str(snapshot.status or "")
        if status == _STATUS_SUCCESS:
            name = (snapshot.display_name or "").strip()
            logger.info("扫码成功 platform=%s account=%s", platform, snapshot.account_id)
            return {
                "ok": True,
                "platform": platform,
                "status": status,
                "account_id": snapshot.account_id,
                "display_name": name or None,
                "message": f"已登录{name}，cookie 已存入账号库" if name else "登录成功，cookie 已存入账号库",
            }
        if status in {_STATUS_FAILED, _STATUS_EXPIRED}:
            logger.warning("扫码失败 platform=%s status=%s", platform, status)
            return {
                "ok": False,
                "platform": platform,
                "status": status,
                "error_code": "login.failed",
                "message": snapshot.detail or "扫码登录失败",
            }
        await asyncio.sleep(_POLL_INTERVAL_S)


async def _push_qr(
    ctx: RunContext,
    platform: str,
    qr_base64: str | None,
    *,
    step_id: str | None = None,
    hint: str | None = None,
) -> None:
    """把二维码推成一帧，挂到本步骤的登录块上；没有码就不推（页面停在 loading）。"""
    if not qr_base64:
        return
    mime, image_b64 = _qr_image(qr_base64)
    await ctx.emit_frame(
        url=f"dingda://login/{platform}",
        title=f"扫码登录 · {platform_label(platform)}",
        hint=hint or "用 App 扫码登录",
        mime=mime,
        image_b64=image_b64,
        step_id=step_id,
    )


def _qr_image(raw: str) -> tuple[str, str]:
    """二维码原文 → ``(mime, base64)``；带 ``data:`` 前缀就从前缀取 mime。"""
    text = (raw or "").strip()
    if text.startswith("data:"):
        head, _, body = text.partition(",")
        mime = head[5:].split(";")[0].strip() or "image/png"
        return mime, body
    return "image/png", text


def _fail(platform: str, code: str, message: str) -> dict[str, object]:
    """失败出参：形状与成功时对齐，只多 error_code / message。"""
    return {"ok": False, "platform": platform or "unknown", "error_code": code, "message": message}


class LoginInput(BaseModel):
    """扫码登录入参。"""

    platform: str = Field(description="要登录的平台：xianyu / xiaohongshu / ali1688")


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="login",
        label="扫码登录 · {platform}",
        description=(
            "要用户掏出手机扫码登录，完成后 cookie 自动存进账号库，后续抓取就能用了。"
            "只在工具报 account.session_expired / account.cookie_required 时调它，"
            "并且**先一句话告诉用户要扫码**再调。一次只登一个平台。"
            "闲鱼等 120 秒、小红书 240 秒、1688 180 秒；超时返回 login.timeout，可以让用户重试。"
        ),
        args=LoginInput,
        fn=login,
        kind="login",
    ),
)
