"""选品 Tool：login（扫码登录并阻塞等待）。

职责：
    某平台 cookie 失效时，拉起扫码登录；向前端推二维码直播帧，
    阻塞直到用户扫码成功 / 失败 / 超时。

设计说明：
    - 复用 ``ChannelQrService``（与设置页扫码同一套 Channel）
    - 成功时落库账号 cookie，供后续 search/product 自动带上
    - 不 import Playwright；Channel 内部经 browser.sync

使用示例：
    out = await run_login(LoginInput(platform="xianyu"))
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from src.channels.types import LoginStatus
from src.contracts.channel import QrStartRequest
from src.domains.channel.qr_service import get_channel_qr_service
from src.shared.errors import AppError

logger = logging.getLogger("dingda.tools.login")

TOOL_NAME = "login"
TOOL_DESCRIPTION = (
    "当 search/product 返回登录过期（account.session_expired）时调用。"
    "拉起指定平台扫码登录，阻塞等待用户手机扫码完成；成功后 cookie 已落库，可立刻重试搜品。"
    "platform：xianyu / xiaohongshu / ali1688。"
)
DEFAULT_TIMEOUT_S = 300.0

_PLATFORM_TIMEOUT: dict[str, int] = {
    "xianyu": 120,
    "xiaohongshu": 240,
    "ali1688": 180,
}
_POLL_INTERVAL_S = 1.5


class LoginInput(BaseModel):
    """扫码登录入参。"""

    platform: str = Field(
        description="要登录的平台：xianyu=闲鱼；xiaohongshu=小红书；ali1688=1688。",
    )


class LoginOutput(BaseModel):
    """扫码登录出参。"""

    ok: bool = True
    platform: str
    status: str
    account_id: str | None = None
    display_name: str | None = None
    detail: str | None = None
    error_code: str | None = None
    message: str | None = None


async def run_login(
    inp: LoginInput,
    *,
    on_live_frame: Any | None = None,
) -> LoginOutput:
    """启动扫码并轮询至终态；期间推送二维码帧。"""
    platform = inp.platform.strip().lower()
    if platform not in _PLATFORM_TIMEOUT:
        return LoginOutput(
            ok=False,
            platform=platform,
            status="failed",
            error_code="login.platform_unsupported",
            message=f"不支持的登录平台：{platform}",
        )

    logger.info("tool start name=login platform=%s", platform)
    service = get_channel_qr_service()
    label = {"xianyu": "闲鱼", "xiaohongshu": "小红书", "ali1688": "1688"}.get(
        platform, platform
    )

    try:
        started = await asyncio.to_thread(
            service.start,
            QrStartRequest(platform=platform),
        )
    except AppError as exc:
        logger.warning("tool failed name=login code=%s", exc.code)
        return LoginOutput(
            ok=False,
            platform=platform,
            status="failed",
            error_code=exc.code,
            message=exc.message,
        )

    session_id = started.session_id
    await _push_qr_frame(
        on_live_frame,
        platform=platform,
        label=label,
        qr_base64=started.qr_base64,
        detail=started.detail or "请用手机扫码登录",
    )

    deadline = asyncio.get_running_loop().time() + float(
        _PLATFORM_TIMEOUT.get(platform, 120)
    )
    last_qr = started.qr_base64 or ""

    try:
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                await asyncio.to_thread(service.cancel, session_id)
                return LoginOutput(
                    ok=False,
                    platform=platform,
                    status=LoginStatus.EXPIRED.value,
                    error_code="login.timeout",
                    message=f"{label}扫码超时，请再调用 login 重试",
                )

            snap = await asyncio.to_thread(service.check, session_id)
            qr = snap.qr_base64 or ""
            if qr and qr != last_qr:
                last_qr = qr
                await _push_qr_frame(
                    on_live_frame,
                    platform=platform,
                    label=label,
                    qr_base64=qr,
                    detail=snap.detail or "请用手机扫码登录",
                )

            status = str(snap.status or "")
            if status == LoginStatus.SUCCESS.value:
                logger.info(
                    "tool done name=login platform=%s account=%s",
                    platform,
                    snap.account_id,
                )
                return LoginOutput(
                    ok=True,
                    platform=platform,
                    status=status,
                    account_id=snap.account_id,
                    display_name=snap.display_name,
                    detail=snap.detail or f"{label}登录成功",
                    message=f"{label}登录成功，可继续 search/product",
                )
            if status in {LoginStatus.FAILED.value, LoginStatus.EXPIRED.value}:
                return LoginOutput(
                    ok=False,
                    platform=platform,
                    status=status,
                    error_code="login.failed",
                    message=snap.detail or f"{label}扫码失败，请重试",
                )

            await asyncio.sleep(min(_POLL_INTERVAL_S, max(0.2, remaining)))
    except Exception as exc:  # noqa: BLE001
        logger.exception("tool failed name=login")
        try:
            await asyncio.to_thread(service.cancel, session_id)
        except Exception:  # noqa: BLE001
            pass
        return LoginOutput(
            ok=False,
            platform=platform,
            status="failed",
            error_code="tool.failed",
            message=str(exc),
        )


async def _push_qr_frame(
    on_live_frame: Any | None,
    *,
    platform: str,
    label: str,
    qr_base64: str | None,
    detail: str,
) -> None:
    if on_live_frame is None or not qr_base64:
        return
    image = qr_base64.strip()
    if image.startswith("data:"):
        # data URL → 拆 mime / b64
        try:
            header, b64 = image.split(",", 1)
            mime = "image/png"
            if "image/" in header:
                mime = header.split("image/")[1].split(";")[0] or "image/png"
                mime = f"image/{mime}" if not mime.startswith("image/") else mime
            payload = {
                "url": f"dingda://login/{platform}",
                "title": f"{label} · 扫码登录",
                "hint": detail,
                "mime": mime if mime.startswith("image/") else "image/png",
                "image_b64": b64,
            }
        except ValueError:
            payload = {
                "url": f"dingda://login/{platform}",
                "title": f"{label} · 扫码登录",
                "hint": detail,
                "mime": "image/png",
                "image_b64": image,
            }
    else:
        payload = {
            "url": f"dingda://login/{platform}",
            "title": f"{label} · 扫码登录",
            "hint": detail,
            "mime": "image/png",
            "image_b64": image,
        }
    try:
        await on_live_frame(payload)
    except Exception:  # noqa: BLE001
        logger.debug("login live frame push failed", exc_info=True)
