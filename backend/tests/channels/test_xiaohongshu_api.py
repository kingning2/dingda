"""小红书 API 原语测试。"""

from __future__ import annotations

from src.channels.xiaohongshu import api


class TestXiaohongshuApi:
    def test_parse_code_status_accepts_both_keys(self) -> None:
        assert api.parse_code_status({"codeStatus": 1}) == 1
        assert api.parse_code_status({"code_status": 3}) == 3

    def test_is_qr_expired(self) -> None:
        assert api.is_qr_expired(3) is True
        assert api.is_qr_expired(2) is False
        assert api.is_qr_expired(0) is False

    def test_merge_session_cookies(self) -> None:
        cookies = {"a1": "token"}
        merged = api.merge_session_cookies(
            cookies,
            {
                "login_info": {
                    "session": "sess-1",
                    "secure_session": "sec-1",
                    "nickname": "昵称",
                    "user_id": "u1",
                }
            },
        )
        assert merged["web_session"] == "sess-1"
        assert merged["web_session_sec"] == "sec-1"

    def test_extract_qr_credentials(self) -> None:
        qr_id, code = api.extract_qr_credentials(
            {"qr_id": "632031729213436637", "code": "384516", "url": "https://xhs.test"}
        )
        assert qr_id == "632031729213436637"
        assert code == "384516"

    def test_poll_status_in_browser(self) -> None:
        class FakePage:
            def evaluate(self, script, arg):
                assert arg["qrId"] == "1"
                assert arg["qrCode"] == "2"
                return {
                    "code": 0,
                    "success": True,
                    "data": {"code_status": 1},
                }

        payload = api.poll_status_in_browser(FakePage(), "1", "2")
        assert api.parse_code_status(payload) == 1

    def test_is_login_success_response(self) -> None:
        class FakeResponse:
            url = "https://edith.xiaohongshu.com/api/sns/web/v1/login/qrcode/status?qr_id=1"
            request = type("Req", (), {"method": "GET"})()

            def json(self):
                return {"data": {"codeStatus": 2, "login_info": {"session": "s"}}}

        assert api.is_login_success_response(FakeResponse()) is True
