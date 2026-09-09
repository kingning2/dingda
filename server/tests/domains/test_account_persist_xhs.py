"""账号落库：小红书假 id 孤儿清理。"""

from __future__ import annotations

from src.domains.account.persist import (
    _is_xhs_session_fallback_id,
    save_login_credentials,
)
from src.infrastructure.db import accounts as account_repo
from src.infrastructure.db.session import set_db_path


class TestXhsOrphanCleanup:
    def test_fallback_id_shape(self) -> None:
        assert _is_xhs_session_fallback_id("xhs:030037adad26") is True
        assert _is_xhs_session_fallback_id("xhs:62be65ce000000001b026a67") is False

    def test_cleanup_same_a1_fallback(self, tmp_path) -> None:
        set_db_path(tmp_path / "accounts.db")
        account_repo.upsert_account(
            account_id="xhs:030037adad26",
            platform="xiaohongshu",
            display_name="新小红书账号",
            avatar_url=None,
            cookie="a1=same-device; web_session=old",
            auto_connect=False,
            auth_valid=True,
            connected=False,
        )
        save_login_credentials(
            platform="xiaohongshu",
            account_id="xhs:62be65ce000000001b026a67",
            display_name="小满技术工作室",
            cookie="a1=same-device; web_session=new",
            avatar_url=None,
        )
        ids = {r.account_id for r in account_repo.list_accounts(platform="xiaohongshu")}
        assert "xhs:62be65ce000000001b026a67" in ids
        assert "xhs:030037adad26" not in ids
