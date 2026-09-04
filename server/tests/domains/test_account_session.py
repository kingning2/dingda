"""账号会话展示态测试。"""

from __future__ import annotations

from src.domains.account.session import build_session_views


def test_xianyu_valid_disconnected() -> None:
    session, actions = build_session_views("xianyu", auth_valid=True, connected=False)
    assert session.label == "未连接"
    assert actions.can_connect is True
    assert actions.can_rescan is False


def test_xianyu_valid_connected() -> None:
    session, actions = build_session_views("xianyu", auth_valid=True, connected=True)
    assert session.label == "已连接"
    assert actions.can_disconnect is True
    assert actions.can_connect is False


def test_xianyu_expired_shows_auth_expired() -> None:
    session, actions = build_session_views("xianyu", auth_valid=False, connected=True)
    assert session.state == "auth_expired"
    assert session.label == "登录过期"
    assert actions.can_rescan is True
    assert actions.can_connect is False


def test_xiaohongshu_valid_shows_logged_in() -> None:
    session, actions = build_session_views("xiaohongshu", auth_valid=True)
    assert session.label == "已登录"
    assert actions.can_rescan is False


def test_xiaohongshu_expired_shows_auth_expired() -> None:
    session, actions = build_session_views("xiaohongshu", auth_valid=False)
    assert session.state == "auth_expired"
    assert actions.can_rescan is True
