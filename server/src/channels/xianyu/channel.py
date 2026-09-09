"""闲鱼扫码登录 Channel（状态机 + 后台轮询）。

职责：
    实现 QrLoginChannel 插座：生成二维码、轮询扫码、成功后拉一次资料并写入 cookie；
    供账号域 HTTP API 与扫码终端使用。

设计说明：
    - 平台：闲鱼（xianyu）
    - 组合 api / renew / risk 模块；Browser 仅用于开页与滑块兜底
    - Tool / Agent 不直接 import 本模块
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from src.browser.sync import submit_on_sync_browser
from src.channels.base import QrLoginChannel
from src.channels.qr_terminal import decode_qr_text_from_png_base64
from src.channels.types import LoginSnapshot, LoginStatus, QrCancelled
from src.channels.xianyu import login as api
from src.channels.xianyu.refresh import profile as fetch_login_profile
from src.channels.xianyu.renew import renew
from src.channels.xianyu.risk import RiskControlError, page_is_punish

logger = logging.getLogger("dingda.channel.xianyu")


@dataclass
class XianyuLoginRuntime:
    qr_base64: str | None = None
    qr_url: str | None = None
    cookies: dict[str, str] | None = None
    local_storage: dict[str, str] | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    scanned: bool = False
    refresh_count: int = 0
    error: str | None = None
    status_detail: str | None = None
    ready: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)


class XianyuQrChannel(QrLoginChannel):
    platform = "xianyu"

    def start_login(self, *, timeout: int = 120) -> XianyuLoginRuntime:
        runtime = XianyuLoginRuntime()
        submit_on_sync_browser(lambda: self._run(runtime, timeout))
        return runtime

    def snapshot(self, runtime: XianyuLoginRuntime) -> LoginSnapshot:
        with runtime.lock:
            if runtime.cookies:
                unb = runtime.cookies.get("unb", "unknown")
                tracknick = str(runtime.cookies.get("tracknick", "")).strip()
                display_name = (
                    runtime.display_name or tracknick or f"闲鱼账号 {unb}"
                )
                return LoginSnapshot(
                    status=LoginStatus.SUCCESS,
                    detail="登录成功！",
                    qr_base64=runtime.qr_base64,
                    qr_url=runtime.qr_url,
                    account_id=f"xy:{unb}",
                    display_name=display_name,
                    avatar_url=runtime.avatar_url,
                    cookie=api.cookie_str(runtime.cookies),
                )
            if runtime.error and not runtime.qr_base64:
                return LoginSnapshot(
                    status=LoginStatus.FAILED,
                    detail=runtime.error,
                )
            if runtime.done.is_set() and runtime.error:
                return LoginSnapshot(
                    status=LoginStatus.FAILED,
                    detail=runtime.error,
                    qr_base64=runtime.qr_base64,
                    qr_url=runtime.qr_url,
                )
            if runtime.done.is_set():
                return LoginSnapshot(
                    status=LoginStatus.EXPIRED,
                    detail="二维码已过期，请重新发起扫码",
                    qr_base64=runtime.qr_base64,
                    qr_url=runtime.qr_url,
                )
            if runtime.scanned:
                return LoginSnapshot(
                    status=LoginStatus.SCANNED,
                    detail=runtime.status_detail or "已扫码，请在手机确认登录",
                    qr_base64=runtime.qr_base64,
                    qr_url=runtime.qr_url,
                )
            return LoginSnapshot(
                status=LoginStatus.WAITING,
                detail=runtime.status_detail,
                qr_base64=runtime.qr_base64,
                qr_url=runtime.qr_url,
            )

    def _try_risk_recovery(
        self,
        runtime: XianyuLoginRuntime,
        *,
        partial_cookies: dict[str, str] | None,
        punish_url: str | None,
        reason: str,
    ) -> bool:
        unb = (partial_cookies or {}).get("unb", "recover")
        account_id = f"qr:{unb}"
        with runtime.lock:
            runtime.status_detail = "检测到风控，正在自动过滑块…"
        logger.info("闲鱼扫码转入风控恢复: %s", reason)

        def _on_status(msg: str) -> None:
            with runtime.lock:
                runtime.status_detail = msg

        ok, detail, cookies = renew(
            partial_cookies,
            account_id=account_id,
            punish_url=punish_url,
            on_status=_on_status,
        )
        if ok and cookies:
            self._complete_login(runtime, cookies)
            logger.info("闲鱼扫码风控恢复成功: %s", detail)
            return True

        with runtime.lock:
            runtime.error = detail or reason
        logger.warning("闲鱼扫码风控恢复失败: %s", detail or reason)
        return False

    def _run(self, runtime: XianyuLoginRuntime, timeout: int) -> None:
        logger.info("闲鱼扫码任务启动（Camoufox 无头浏览器）")
        # 从开浏览器到第一张二维码写入 runtime，对应前端「正在生成二维码」
        qr_started_at = time.perf_counter()
        partial_cookies: dict[str, str] | None = None
        punish_url: str | None = None
        qr_started = False
        try:
            with api.open_login_page() as (page, frame):
                qr_base64, qr_url = api.capture_qr(frame)
                if not qr_base64:
                    if page_is_punish(page.url):
                        punish_url = page.url
                        partial_cookies = api.cookie_map(page.context.cookies())
                        raise RiskControlError("登录页触发风控验证")
                    raise RuntimeError("无法获取闲鱼二维码图片")
                if not qr_url:
                    qr_url = decode_qr_text_from_png_base64(qr_base64)

                with runtime.lock:
                    runtime.qr_base64 = qr_base64
                    runtime.qr_url = qr_url
                runtime.ready.set()
                qr_started = True
                elapsed = time.perf_counter() - qr_started_at
                logger.info(
                    "闲鱼二维码已生成 elapsed=%.2fs elapsed_ms=%d",
                    elapsed,
                    int(elapsed * 1000),
                )
                baseline = api.cookie_map(page.context.cookies())

                deadline = time.monotonic() + timeout
                last_refresh = time.monotonic()

                while time.monotonic() < deadline:
                    if runtime.cancel.is_set():
                        raise QrCancelled()
                    if page_is_punish(page.url):
                        punish_url = page.url
                        partial_cookies = api.cookie_map(page.context.cookies())
                        raise RiskControlError("扫码过程中触发风控验证")

                    cookies_list = page.context.cookies()
                    current = api.cookie_map(cookies_list)
                    if api.has_login_completed(cookies_list, baseline):
                        self._complete_login(runtime, current)
                        logger.info("闲鱼扫码登录成功")
                        return

                    with runtime.lock:
                        scanned = runtime.scanned
                    if scanned and api.has_all_login_cookies(cookies_list):
                        self._complete_login(runtime, current)
                        logger.info("闲鱼扫码登录成功（手机已确认）")
                        return

                    if api.has_scanned_cookies(cookies_list, baseline):
                        with runtime.lock:
                            if not runtime.scanned:
                                logger.info("闲鱼二维码已扫描，等待手机确认")
                            runtime.scanned = True

                    if time.monotonic() - last_refresh >= api.QR_REFRESH_INTERVAL_S:
                        runtime.refresh_count += 1
                        if runtime.refresh_count > api.QR_MAX_REFRESHES:
                            partial_cookies = current
                            raise TimeoutError(
                                f"二维码已刷新 {api.QR_MAX_REFRESHES} 次仍未登录，请重试"
                            )
                        new_b64, new_url = api.capture_qr(frame)
                        if new_b64:
                            if not new_url:
                                new_url = decode_qr_text_from_png_base64(new_b64)
                            with runtime.lock:
                                runtime.qr_base64 = new_b64
                                runtime.qr_url = new_url
                                runtime.scanned = False
                            baseline = api.cookie_map(page.context.cookies())
                            logger.info(
                                "闲鱼二维码已刷新 (%s/%s)",
                                runtime.refresh_count,
                                api.QR_MAX_REFRESHES,
                            )
                        last_refresh = time.monotonic()

                    time.sleep(0.2)

                if runtime.cancel.is_set():
                    raise QrCancelled()
                partial_cookies = api.cookie_map(page.context.cookies())
                raise TimeoutError("扫码超时，请重试")
        except QrCancelled:
            logger.info("闲鱼扫码已取消")
        except Exception as exc:
            logger.warning("闲鱼扫码失败: %s", exc)
            if qr_started or punish_url or isinstance(exc, (RiskControlError, TimeoutError)):
                if self._try_risk_recovery(
                    runtime,
                    partial_cookies=partial_cookies,
                    punish_url=punish_url,
                    reason=str(exc),
                ):
                    return
            elif not runtime.error:
                with runtime.lock:
                    runtime.error = str(exc)
        finally:
            runtime.ready.set()
            runtime.done.set()

    def _complete_login(
        self,
        runtime: XianyuLoginRuntime,
        cookies: dict[str, str],
    ) -> None:
        """登录 cookie 就绪后拉一次 user.page.nav，写入昵称头像。"""
        name, avatar = fetch_login_profile(api.cookie_str(cookies))
        unb = cookies.get("unb", "unknown")
        tracknick = str(cookies.get("tracknick", "")).strip()
        display_name = (name or tracknick or f"闲鱼账号 {unb}").strip()
        logger.info(
            "闲鱼登录资料 name=%s avatar=%s",
            bool(name),
            bool(avatar),
        )
        with runtime.lock:
            runtime.cookies = cookies
            runtime.display_name = display_name
            runtime.avatar_url = avatar
