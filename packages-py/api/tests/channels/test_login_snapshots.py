"""channels 登录状态机快照测试（无浏览器）。"""

from __future__ import annotations

import threading

from channels.types import LoginStatus
from channels.xianyu.channel import XianyuLoginRuntime, XianyuQrChannel
from channels.xiaohongshu.channel import XiaohongshuLoginRuntime, XiaohongshuQrChannel


class TestXianyuSnapshot:
    def test_waiting(self) -> None:
        runtime = XianyuLoginRuntime(qr_base64="ZmFrZQ==", qr_url="https://example.com/qr")
        snap = XianyuQrChannel().snapshot(runtime)
        assert snap.status == LoginStatus.WAITING
        assert snap.qr_base64 == "ZmFrZQ=="

    def test_scanned(self) -> None:
        runtime = XianyuLoginRuntime(
            qr_base64="ZmFrZQ==",
            scanned=True,
        )
        snap = XianyuQrChannel().snapshot(runtime)
        assert snap.status == LoginStatus.SCANNED
        assert snap.detail == "已扫码，请在手机确认登录"

    def test_success(self) -> None:
        runtime = XianyuLoginRuntime(
            cookies={"unb": "123", "_m_h5_tk": "t", "cookie2": "c"},
            qr_base64="ZmFrZQ==",
        )
        snap = XianyuQrChannel().snapshot(runtime)
        assert snap.status == LoginStatus.SUCCESS
        assert snap.account_id == "xy:123"
        assert snap.cookie

    def test_failed_without_qr(self) -> None:
        runtime = XianyuLoginRuntime(error="启动失败")
        snap = XianyuQrChannel().snapshot(runtime)
        assert snap.status == LoginStatus.FAILED

    def test_expired_when_done(self) -> None:
        runtime = XianyuLoginRuntime(qr_base64="ZmFrZQ==", done=threading.Event())
        runtime.done.set()
        snap = XianyuQrChannel().snapshot(runtime)
        assert snap.status == LoginStatus.EXPIRED


class TestXiaohongshuSnapshot:
    def test_waiting(self) -> None:
        runtime = XiaohongshuLoginRuntime(qr_base64="ZmFrZQ==", qr_url="https://xhs.test/qr")
        snap = XiaohongshuQrChannel().snapshot(runtime)
        assert snap.status == LoginStatus.WAITING

    def test_scanned(self) -> None:
        runtime = XiaohongshuLoginRuntime(qr_base64="ZmFrZQ==", code_status=1)
        snap = XiaohongshuQrChannel().snapshot(runtime)
        assert snap.status == LoginStatus.SCANNED

    def test_success(self) -> None:
        runtime = XiaohongshuLoginRuntime(
            cookie="a1=x; web_session=y",
            account_id="xhs:u1",
            display_name="昵称",
        )
        snap = XiaohongshuQrChannel().snapshot(runtime)
        assert snap.status == LoginStatus.SUCCESS
        assert snap.display_name == "昵称"

    def test_ignore_qr_create_after_login_complete(self) -> None:
        from unittest.mock import MagicMock

        runtime = XiaohongshuLoginRuntime(qr_base64="old", code_status=2)
        login_complete = threading.Event()
        login_complete.set()
        response = MagicMock()
        response.url = "https://edith.xiaohongshu.com/api/sns/web/v1/login/qrcode/create"
        response.request.method = "POST"

        XiaohongshuQrChannel()._handle_qr_response(
            response,
            MagicMock(),
            runtime,
            initial_qr_set={"value": True},
            expired_pending={"value": False},
            completion_holder={"data": {"code_status": 2}},
            login_complete=login_complete,
        )
        assert runtime.qr_base64 == "old"
        assert runtime.code_status == 2
