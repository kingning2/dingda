"""账号会话展示态（由后端根据平台与登录有效性组装）。"""

from __future__ import annotations

from contracts.account import (
    AccountActionsView,
    AccountPlatform,
    AccountSessionView,
)

_SESSION_CONNECTED = AccountSessionView(
    state="connected",
    label="已连接",
    hint=None,
    badge_class="bg-emerald-500/15 text-emerald-600",
)
_SESSION_DISCONNECTED = AccountSessionView(
    state="disconnected",
    label="未连接",
    hint=None,
    badge_class="bg-muted text-muted-foreground",
)
_SESSION_LOGGED_IN = AccountSessionView(
    state="connected",
    label="已登录",
    hint=None,
    badge_class="bg-emerald-500/15 text-emerald-600",
)
_SESSION_AUTH_EXPIRED = AccountSessionView(
    state="auth_expired",
    label="登录过期",
    hint="登录态已过期，请重新扫码",
    badge_class="bg-orange-500/15 text-orange-700",
)

_ACTIONS_XIANYU_DISCONNECTED = AccountActionsView(
    can_connect=True,
    can_disconnect=False,
    can_rescan=False,
)
_ACTIONS_XIANYU_CONNECTED = AccountActionsView(
    can_connect=False,
    can_disconnect=True,
    can_rescan=False,
)
_ACTIONS_XIANYU_EXPIRED = AccountActionsView(
    can_connect=False,
    can_disconnect=False,
    can_rescan=True,
)
_ACTIONS_LOGIN_OK = AccountActionsView(
    can_connect=False,
    can_disconnect=False,
    can_rescan=False,
)
_ACTIONS_LOGIN_EXPIRED = AccountActionsView(
    can_connect=False,
    can_disconnect=False,
    can_rescan=True,
)


def build_session_views(
    platform: AccountPlatform,
    *,
    auth_valid: bool,
    connected: bool = False,
) -> tuple[AccountSessionView, AccountActionsView]:
    if not auth_valid:
        if platform == "xianyu":
            return _SESSION_AUTH_EXPIRED, _ACTIONS_XIANYU_EXPIRED
        return _SESSION_AUTH_EXPIRED, _ACTIONS_LOGIN_EXPIRED

    if platform == "xianyu":
        if connected:
            return _SESSION_CONNECTED, _ACTIONS_XIANYU_CONNECTED
        return _SESSION_DISCONNECTED, _ACTIONS_XIANYU_DISCONNECTED

    return _SESSION_LOGGED_IN, _ACTIONS_LOGIN_OK
