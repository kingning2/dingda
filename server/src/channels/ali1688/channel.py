"""1688 clawhub 扫码登录 Channel（取 AK）。

职责：
    实现 QrLoginChannel：打开 clawhub 登录弹窗、出码、等扫码确认、抽取 AK 并 save_ak。
    供账号域 HTTP 扫码弹窗使用。

设计说明：
    - 经 browser.sync（Camoufox 同步页），不直连 Playwright/Camoufox import
    - 成功后 cookie 字段存 raw AK，便于账号列表落库与前端刷新

使用示例：
    channel = Ali1688QrChannel()
    runtime = channel.start_login(timeout=180)
    snap = channel.snapshot(runtime)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from src.browser.sync import submit_on_sync_browser, sync_headless_page
from src.channels.ali1688.ak import extract_ak_keys, save_ak
from src.channels.ali1688 import login as clawhub
from src.channels.base import QrLoginChannel
from src.channels.types import LoginSnapshot, LoginStatus, QrCancelled

logger = logging.getLogger("dingda.channel.ali1688")


@dataclass
class Ali1688LoginRuntime:
    """扫码运行时状态。"""

    qr_base64: str | None = None
    qr_url: str | None = None
    cookie: str | None = None  # raw AK
    account_id: str | None = None
    display_name: str | None = None
    scanned: bool = False
    error: str | None = None
    status_detail: str | None = None
    ready: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)


class Ali1688QrChannel(QrLoginChannel):
    """1688 插头：clawhub 扫码取 AK。"""

    platform = "ali1688"

    def start_login(self, *, timeout: int = 180) -> Ali1688LoginRuntime:
        """启动后台扫码任务。"""
        runtime = Ali1688LoginRuntime()
        submit_on_sync_browser(lambda: self._run(runtime, timeout))
        return runtime

    def snapshot(self, runtime: Ali1688LoginRuntime) -> LoginSnapshot:
        """读取当前扫码快照。"""
        with runtime.lock:
            if runtime.cookie:
                return LoginSnapshot(
                    status=LoginStatus.SUCCESS,
                    detail="登录成功，AK 已保存",
                    qr_base64=runtime.qr_base64,
                    qr_url=runtime.qr_url,
                    account_id=runtime.account_id,
                    display_name=runtime.display_name,
                    cookie=runtime.cookie,
                )
            if runtime.error and not runtime.qr_base64:
                return LoginSnapshot(status=LoginStatus.FAILED, detail=runtime.error)
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
                detail=runtime.status_detail or "请使用 1688 / 淘宝 App 扫码",
                qr_base64=runtime.qr_base64,
                qr_url=runtime.qr_url,
            )

    def _run(self, runtime: Ali1688LoginRuntime, timeout: int) -> None:
        """同步浏览器线程：出码 → 等登录 → 抽 AK。"""
        try:
            logger.info("1688 clawhub 扫码任务启动 timeout=%s", timeout)
            with sync_headless_page() as page:
                if runtime.cancel.is_set():
                    raise QrCancelled()

                clawhub.open_login_modal(page)
                if runtime.cancel.is_set():
                    raise QrCancelled()

                png_b64 = clawhub.capture_qr_base64(page, timeout_ms=25_000)
                with runtime.lock:
                    runtime.qr_base64 = png_b64
                    runtime.qr_url = clawhub.CLAWHUB_URL
                    runtime.status_detail = "请使用 1688 / 淘宝 App 扫码"
                runtime.ready.set()
                logger.info("1688 二维码已就绪 bytes=%s", len(png_b64))

                deadline = time.monotonic() + max(30, timeout)
                while time.monotonic() < deadline:
                    if runtime.cancel.is_set():
                        raise QrCancelled()

                    scanned = runtime.scanned or clawhub.looks_scanned(page)
                    if scanned and not runtime.scanned:
                        with runtime.lock:
                            runtime.scanned = True
                            runtime.status_detail = "已扫码，请在手机确认登录"
                        logger.info("1688 已扫码，加快轮询")

                    # 已扫码后：弹窗收起即视为登录成功（不要再点开登录）
                    if clawhub.is_logged_in(page) or (
                        runtime.scanned and clawhub.login_completed_after_scan(page)
                    ):
                        logger.info("1688 clawhub 登录成功，开始抽取 AK")
                        with runtime.lock:
                            runtime.status_detail = "登录成功，正在读取 AK…"
                        raw_ak = clawhub.extract_ak_from_page(page)
                        self._publish_success(runtime, raw_ak)
                        return

                    # 仅未扫码时，弹窗被关才重开；已扫码禁止重开，否则会打断跳转
                    if (
                        not runtime.scanned
                        and not clawhub.login_modal_visible(page)
                        and not clawhub.is_logged_in(page)
                    ):
                        try:
                            clawhub.open_login_modal(page)
                            png_b64 = clawhub.capture_qr_base64(page)
                            with runtime.lock:
                                runtime.qr_base64 = png_b64
                                runtime.status_detail = "二维码已刷新，请重新扫码"
                        except Exception:
                            pass

                    # 已扫码后加快感知确认；未扫码保持 1.2s
                    page.wait_for_timeout(400 if runtime.scanned else 1200)

                with runtime.lock:
                    runtime.error = "扫码超时，请重试"
                logger.warning("1688 扫码超时")
        except QrCancelled:
            logger.info("1688 扫码已取消")
            with runtime.lock:
                runtime.error = "已取消扫码"
        except Exception as exc:
            logger.exception("1688 扫码失败")
            with runtime.lock:
                runtime.error = str(exc) or "扫码失败"
        finally:
            runtime.ready.set()
            runtime.done.set()

    def _publish_success(self, runtime: Ali1688LoginRuntime, raw_ak: str) -> None:
        """落盘 AK 并写入 runtime。"""
        save_ak(raw_ak)
        ak_id, _secret = extract_ak_keys(raw_ak)
        account_id = f"ali1688:{ak_id or 'ak'}"
        display = f"1688 AK {(ak_id or '')[:8]}".strip()
        with runtime.lock:
            runtime.cookie = raw_ak
            runtime.account_id = account_id
            runtime.display_name = display
            runtime.status_detail = "AK 已保存"
        logger.info("1688 AK 已保存 account_id=%s", account_id)
