"""accounts 仓库 auth_valid 写入守卫测试：判定绑定 cookie 版本。"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from infrastructure.db import accounts as account_repo
from infrastructure.db.session import set_db_path


@pytest.fixture(autouse=True)
def _temp_db(tmp_path: Path) -> None:
    set_db_path(tmp_path / "accounts.db")
    yield
    set_db_path(None)


def _upsert(account_id: str, cookie: str, *, auth_valid: bool) -> None:
    account_repo.upsert_account(
        account_id=account_id,
        platform="xianyu",
        display_name="测",
        cookie=cookie,
        auth_valid=auth_valid,
        connected=True,
    )


def test_stale_probe_cannot_downgrade_fresh_login() -> None:
    """旧 cookie 的失败判定不得降级重新扫码后的新登录态。"""
    _upsert("xy-1", "cookie_old=1", auth_valid=True)
    _upsert("xy-1", "cookie_new=2", auth_valid=True)

    applied = account_repo.set_auth_valid("xy-1", False, cookie_seen="cookie_old=1")

    assert applied is False
    row = account_repo.get_account("xy-1")
    assert row.auth_valid is True
    assert row.cookie == "cookie_new=2"


def test_probe_downgrade_applies_when_cookie_matches() -> None:
    """cookie 未被换过时，探活失败判定正常生效。"""
    _upsert("xy-2", "cookie_a=1", auth_valid=True)

    applied = account_repo.set_auth_valid("xy-2", False, cookie_seen="cookie_a=1")

    assert applied is True
    assert account_repo.get_account("xy-2").auth_valid is False


def test_downgrade_transition_is_logged(caplog) -> None:
    """True→False 必须留痕，静默翻转从此绝迹。"""
    _upsert("xy-3", "cookie_a=1", auth_valid=True)
    with caplog.at_level(logging.INFO, logger="dingda.infra.accounts"):
        account_repo.set_auth_valid("xy-3", False, cookie_seen="cookie_a=1")

    assert any("登录态变更" in r.message for r in caplog.records)


def test_set_auth_valid_missing_account_returns_false() -> None:
    assert account_repo.set_auth_valid("xy-none", True) is False
