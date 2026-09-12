"""小红书扫码登录 Channel。"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from browser.sync import submit_on_sync_browser, sync_headless_page
from channels.base import QrLoginChannel
from channels.types import LoginSnapshot, LoginStatus, QrCancelled
from channels.xiaohongshu import login as api

logger = logging.getLogger("dingda.channel.xiaohongshu")


@dataclass
class XiaohongshuLoginRuntime:
    code_status: int = 0
    qr_base64: str | None = None
    qr_url: str | None = None
    cookie: str | None = None
    account_id: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    refresh_count: int = 0
    error: str | None = None
    ready: threading.Event = field(default_factory=threading.Event)
    done: threading.Event = field(default_factory=threading.Event)
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)


class XiaohongshuQrChannel(QrLoginChannel):
    platform = "xiaohongshu"

    def start_login(self, *, timeout: int = 240) -> XiaohongshuLoginRuntime:
        runtime = XiaohongshuLoginRuntime()
        submit_on_sync_browser(lambda: self._run(runtime, timeout))
        return runtime

    def snapshot(self, runtime: XiaohongshuLoginRuntime) -> LoginSnapshot:
        with runtime.lock:
            if runtime.error and not runtime.qr_base64:
                return LoginSnapshot(status=LoginStatus.FAILED, detail=runtime.error)
            if runtime.cookie:
                return LoginSnapshot(
                    status=LoginStatus.SUCCESS,
                    detail="登录成功！",
                    qr_base64=runtime.qr_base64,
                    qr_url=runtime.qr_url,
                    account_id=runtime.account_id,
                    display_name=runtime.display_name,
                    avatar_url=runtime.avatar_url,
                    cookie=runtime.cookie,
                )
            # code_status=2 但 cookie 未写：正在读昵称，对外仍当「已扫码」避免假 SUCCESS
            if runtime.code_status in (1, 2):
                return LoginSnapshot(
                    status=LoginStatus.SCANNED,
                    detail=(
                        "正在读取账号资料…"
                        if runtime.code_status == 2
                        else "已扫码，请在手机确认登录"
                    ),
                    qr_base64=runtime.qr_base64,
                    qr_url=runtime.qr_url,
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
            return LoginSnapshot(
                status=LoginStatus.WAITING,
                qr_base64=runtime.qr_base64,
                qr_url=runtime.qr_url,
            )

    def _maybe_publish_login(
        self,
        page: Any,
        runtime: XiaohongshuLoginRuntime,
        completion_holder: dict[str, Any],
        login_complete: threading.Event,
    ) -> None:
        if not login_complete.is_set() or not completion_holder.get("data") or runtime.cookie:
            return
        try:
            account_id, *_ = api.publish_login_success(
                runtime,
                page,
                completion_holder["data"],
            )
            logger.info("小红书扫码登录成功: %s name=%s avatar=%s", account_id, runtime.display_name, bool(runtime.avatar_url))
        except Exception as exc:
            logger.warning("小红书登录态落盘失败: %s", exc)

    def _handle_qr_response(
        self,
        response: Any,
        page: Any,
        runtime: XiaohongshuLoginRuntime,
        *,
        initial_qr_set: dict[str, bool],
        expired_pending: dict[str, bool],
        completion_holder: dict[str, Any],
        login_complete: threading.Event,
    ) -> None:
        url = response.url
        try:
            if api.QR_CREATE_ENDPOINT in url and response.request.method == "POST":
                if not initial_qr_set["value"]:
                    return
                # 已确认登录后跳探索页也可能再打 create，不能刷新二维码、打回 waiting
                if login_complete.is_set() or completion_holder.get("data"):
                    logger.info("忽略登录后的二维码 create 响应")
                    return
                with runtime.lock:
                    if runtime.cookie or runtime.code_status == 2:
                        logger.info("忽略登录后的二维码 create 响应")
                        return
                payload = api.browser_payload(response)
                qr_url, png = api.apply_qr_payload(payload)
                if qr_url and png:
                    with runtime.lock:
                        runtime.qr_url = qr_url
                        runtime.qr_base64 = png
                        runtime.code_status = 0
                    expired_pending["value"] = False
                    logger.info(
                        "小红书二维码已更新 (%s/%s)",
                        runtime.refresh_count,
                        api.QR_MAX_REFRESHES,
                    )
                return

            if api.QR_USERINFO_ENDPOINT not in url and not api.is_status_poll_response(
                response
            ):
                return

            payload = api.browser_payload(response)
            api.apply_status_payload(
                payload,
                runtime=runtime,
                expired_pending=expired_pending,
                completion_holder=completion_holder,
                login_complete=login_complete,
            )
        except Exception as exc:
            logger.debug("忽略非 QR 响应 %s: %s", url, exc)

    def _run(self, runtime: XiaohongshuLoginRuntime, timeout: int) -> None:
        login_complete = threading.Event()
        completion_holder: dict[str, Any] = {}
        expired_pending = {"value": False}
        initial_qr_set = {"value": False}
        qr_id = ""
        qr_code = ""

        try:
            logger.info("小红书扫码任务启动（Camoufox 无头浏览器）")
            # 从开浏览器到 create 接口返回并画出 PNG，对应前端「正在生成二维码」
            qr_started_at = time.perf_counter()
            with sync_headless_page() as page:
                if runtime.cancel.is_set():
                    raise QrCancelled()
                page.on(
                    "response",
                    lambda response: self._handle_qr_response(
                        response,
                        page,
                        runtime,
                        initial_qr_set=initial_qr_set,
                        expired_pending=expired_pending,
                        completion_holder=completion_holder,
                        login_complete=login_complete,
                    ),
                )

                # 打开登录页，并等到二维码 create 接口返回（通常比启动浏览器更久）
                nav_started = time.perf_counter()
                with page.expect_response(api._matches_qr_create, timeout=20_000) as qr_response_info:
                    page.goto(api.LOGIN_URL, wait_until="domcontentloaded", timeout=20_000)
                    logger.info(
                        "打开登录页完成 elapsed=%.2fs elapsed_ms=%d",
                        time.perf_counter() - nav_started,
                        int((time.perf_counter() - nav_started) * 1000),
                    )
                logger.info(
                    "二维码 create 接口已返回 elapsed=%.2fs elapsed_ms=%d",
                    time.perf_counter() - nav_started,
                    int((time.perf_counter() - nav_started) * 1000),
                )

                qr_payload = api.browser_payload(qr_response_info.value)
                qr_url, png = api.apply_qr_payload(qr_payload)
                qr_id, qr_code = api.extract_qr_credentials(qr_payload)
                if not qr_url or not png:
                    raise ValueError("未获取到小红书二维码 URL")
                if not qr_id or not qr_code:
                    raise ValueError("二维码 create 响应缺少 qr_id / code")

                with runtime.lock:
                    runtime.qr_url = qr_url
                    runtime.qr_base64 = png
                initial_qr_set["value"] = True
                runtime.ready.set()
                elapsed = time.perf_counter() - qr_started_at
                logger.info(
                    "小红书二维码已生成 qr_id=%s elapsed=%.2fs elapsed_ms=%d",
                    qr_id,
                    elapsed,
                    int(elapsed * 1000),
                )

                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if runtime.cancel.is_set():
                        raise QrCancelled()
                    if login_complete.is_set():
                        break

                    # 必须用 Playwright 等待以派发 response 事件；time.sleep 会卡住被动监听
                    try:
                        response = page.wait_for_response(
                            lambda resp: api.QR_USERINFO_ENDPOINT in resp.url
                            or api.is_status_poll_response(resp),
                            timeout=800,
                        )
                        payload = api.browser_payload(response)
                        api.apply_status_payload(
                            payload,
                            runtime=runtime,
                            expired_pending=expired_pending,
                            completion_holder=completion_holder,
                            login_complete=login_complete,
                        )
                    except Exception:
                        pass

                    if runtime.cancel.is_set():
                        raise QrCancelled()
                    if login_complete.is_set():
                        break

                    try:
                        status_payload = api.poll_status_in_browser(page, qr_id, qr_code)
                        api.apply_status_payload(
                            status_payload,
                            runtime=runtime,
                            expired_pending=expired_pending,
                            completion_holder=completion_holder,
                            login_complete=login_complete,
                        )
                    except Exception as exc:
                        logger.debug("小红书主动 status 轮询: %s", exc)

                    if runtime.cancel.is_set():
                        raise QrCancelled()
                    if login_complete.is_set():
                        break

                    if not expired_pending["value"]:
                        page.wait_for_timeout(300)
                        continue

                    # 手机已确认后不要刷二维码，只等 session
                    if runtime.code_status == 2:
                        expired_pending["value"] = False
                        page.wait_for_timeout(300)
                        continue

                    expired_pending["value"] = False
                    with runtime.lock:
                        runtime.refresh_count += 1
                        if runtime.refresh_count > api.QR_MAX_REFRESHES:
                            raise TimeoutError(
                                f"二维码已刷新 {api.QR_MAX_REFRESHES} 次仍未登录，请重试"
                            )

                    refresh_payload = api.trigger_qr_refresh(page)
                    qr_url, png = api.apply_qr_payload(refresh_payload)
                    qr_id, qr_code = api.extract_qr_credentials(refresh_payload)
                    if qr_url and png and qr_id and qr_code:
                        with runtime.lock:
                            runtime.qr_url = qr_url
                            runtime.qr_base64 = png
                            runtime.code_status = 0
                        logger.info(
                            "小红书二维码已刷新 (%s/%s) qr_id=%s",
                            runtime.refresh_count,
                            api.QR_MAX_REFRESHES,
                            qr_id,
                        )

                if runtime.cancel.is_set():
                    raise QrCancelled()
                if not completion_holder.get("data"):
                    raise TimeoutError("扫码超时，请重试")

                # userinfo 可能先报成功但没有 session：再补拉 status
                if not api._has_login_session(completion_holder.get("data")):
                    api.wait_for_login_session(
                        page,
                        qr_id=qr_id,
                        qr_code=qr_code,
                        runtime=runtime,
                        completion_holder=completion_holder,
                        login_complete=login_complete,
                        expired_pending=expired_pending,
                    )

                if not runtime.cookie:
                    self._maybe_publish_login(
                        page,
                        runtime,
                        completion_holder,
                        login_complete,
                    )
        except QrCancelled:
            logger.info("小红书扫码已取消")
        except ImportError as exc:
            logger.warning("小红书扫码失败: %s", exc)
            with runtime.lock:
                runtime.error = str(exc)
        except Exception as exc:
            logger.warning("小红书扫码失败: %s", exc)
            with runtime.lock:
                runtime.error = str(exc)
        finally:
            runtime.ready.set()
            runtime.done.set()
