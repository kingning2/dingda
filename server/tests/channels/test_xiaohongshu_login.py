"""小红书 API 原语测试。"""

from __future__ import annotations

from src.channels.xiaohongshu import login as api


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

    def test_profile_from_user_me(self) -> None:
        profile = api.profile_from_user_me(
            {
                "desc": "简介",
                "gender": 0,
                "images": "https://sns-avatar-qc.xhscdn.com/avatar/a.webp",
                "imageb": "https://sns-avatar-qc.xhscdn.com/avatar/b.webp",
                "guest": False,
                "red_id": "42071352899",
                "user_id": "692e3c0900000000370038ec",
                "nickname": "小满技术工作室",
            }
        )
        assert profile["nickname"] == "小满技术工作室"
        assert profile["avatar_url"] == "https://sns-avatar-qc.xhscdn.com/avatar/a.webp"
        assert profile["user_id"] == "692e3c0900000000370038ec"

    def test_profile_from_user_me_skips_guest(self) -> None:
        assert api.profile_from_user_me({"guest": True, "nickname": "x"}) == {}

    def test_profile_from_user_info_userId(self) -> None:
        profile = api.profile_from_user_me(
            {
                "nickname": "小满",
                "images": "https://img.test/a.png",
                "userId": "u1",
                "guest": False,
            }
        )
        assert profile["user_id"] == "u1"

    def test_read_page_user_info(self) -> None:
        class FakePage:
            def wait_for_function(self, script, timeout):
                return None

            def evaluate(self, script):
                return {
                    "nickname": "小满技术工作室",
                    "images": "https://img.test/a.png",
                    "userId": "692e3c0900000000370038ec",
                    "guest": False,
                }

        profile = api.read_page_user_info(FakePage())
        assert profile["nickname"] == "小满技术工作室"
        assert profile["avatar_url"] == "https://img.test/a.png"
        assert profile["user_id"] == "692e3c0900000000370038ec"

    def test_build_account_profile_top_level_userId(self) -> None:
        account_id, name, _avatar = api.build_account_profile(
            {"web_session": "abcdefghijklxxxx"},
            {
                "codeStatus": 2,
                "userId": "692e3c0900000000370038ec",
                "result": "小满技术工作室",
            },
            None,
        )
        assert account_id == "xhs:692e3c0900000000370038ec"
        assert name == "小满技术工作室"

    def test_profile_from_otherinfo_shape(self) -> None:
        class FakeResp:
            def json(self):
                return {
                    "code": 0,
                    "data": {
                        "basic_info": {
                            "nickname": "小满技术工作室",
                            "imageb": "https://img.test/a.png",
                            "user_id": "692e3c0900000000370038ec",
                        }
                    },
                }

        profile = api._profile_from_response(FakeResp())
        assert profile["nickname"] == "小满技术工作室"
        assert profile["user_id"] == "692e3c0900000000370038ec"

    def test_build_account_profile_prefers_completion_over_settled(self) -> None:
        account_id, name, avatar = api.build_account_profile(
            {"web_session": "sess"},
            {"userId": "692e3c0900000000370038ec"},
            {
                "nickname": "小满技术工作室",
                "avatar_url": "https://sns-avatar-qc.xhscdn.com/avatar/a.webp",
                "user_id": "6a9e7be90000000013031c06",  # guest 误读
            },
        )
        assert account_id == "xhs:692e3c0900000000370038ec"
        assert name == "小满技术工作室"
        assert avatar == "https://sns-avatar-qc.xhscdn.com/avatar/a.webp"

    def test_build_account_profile_userId_camel(self) -> None:
        account_id, name, _avatar = api.build_account_profile(
            {"web_session": "abcdefghijklxxxx"},
            {"login_info": {"userId": "uid-camel", "nickname": "驼峰"}},
            None,
        )
        assert account_id == "xhs:uid-camel"
        assert name == "驼峰"

    def test_build_account_profile_nested_login_info(self) -> None:
        account_id, name, _avatar = api.build_account_profile(
            {"web_session": "abcdefghijklxxxx"},
            {"login_info": {"user_id": "62be65ce000000001b026a67"}},
            None,
        )
        assert account_id == "xhs:62be65ce000000001b026a67"
        assert name == "新小红书账号"

    def test_completion_richness_prefers_user_id(self) -> None:
        weak = {"login_info": {"session": "s"}}
        strong = {"login_info": {"session": "s", "user_id": "u1"}}
        assert api._completion_richness(strong) > api._completion_richness(weak)

    def test_build_account_profile_result_nickname(self) -> None:
        account_id, name, _avatar = api.build_account_profile(
            {"web_session": "abcdefghijklxxxx"},
            {
                "userId": "692e3c0900000000370038ec",
                "result": {"nickname": "小满技术工作室"},
            },
            None,
        )
        assert account_id == "xhs:692e3c0900000000370038ec"
        assert name == "小满技术工作室"

    def test_read_page_user_info_soft_fail(self) -> None:
        class FakePage:
            def evaluate(self, script):
                raise RuntimeError("no state")

        assert api.read_page_user_info(FakePage()) == {}

    def test_apply_status_waits_for_session(self) -> None:
        class Runtime:
            code_status = 0
            lock = __import__("threading").Lock()

        runtime = Runtime()
        holder: dict = {}
        complete = __import__("threading").Event()
        expired = {"value": False}

        api.apply_status_payload(
            {"codeStatus": 2, "userId": "u1", "result": {"success": True}},
            runtime=runtime,
            expired_pending=expired,
            completion_holder=holder,
            login_complete=complete,
        )
        assert runtime.code_status == 2
        assert complete.is_set() is False
        assert holder["data"]["userId"] == "u1"

        api.apply_status_payload(
            {
                "code_status": 2,
                "login_info": {"session": "sess-1", "user_id": "u1"},
            },
            runtime=runtime,
            expired_pending=expired,
            completion_holder=holder,
            login_complete=complete,
        )
        assert complete.is_set() is True
        assert api._has_login_session(holder["data"]) is True

    def test_profile_from_response_skips_guest(self) -> None:
        class FakeResp:
            def json(self):
                return {"code": 0, "data": {"guest": True, "user_id": "guest-id"}}

        assert api._profile_from_response(FakeResp()) == {}

    def test_is_login_success_response(self) -> None:
        class FakeResponse:
            url = "https://edith.xiaohongshu.com/api/sns/web/v1/login/qrcode/status?qr_id=1"
            request = type("Req", (), {"method": "GET"})()

            def json(self):
                return {"data": {"codeStatus": 2, "login_info": {"session": "s"}}}

        assert api.is_login_success_response(FakeResponse()) is True
