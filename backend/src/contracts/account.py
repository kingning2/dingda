"""账号持久化契约（SQLite 存储层对外）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AccountPlatform = Literal["xianyu", "ali1688", "xiaohongshu"]


class AccountSessionView(BaseModel):
    state: str
    label: str
    hint: str | None = None
    badge_class: str


class AccountActionsView(BaseModel):
    can_connect: bool
    can_disconnect: bool
    can_rescan: bool


class AccountRecord(BaseModel):
    account_id: str
    platform: AccountPlatform
    display_name: str
    avatar_url: str | None = None
    cookie: str
    status: str = "active"
    status_label: str = "启用"
    has_cookie: bool = True
    auto_connect: bool = False
    auth_valid: bool = True
    session: AccountSessionView
    actions: AccountActionsView


class AccountListResponse(BaseModel):
    ok: bool = True
    items: list[AccountRecord]


class AccountPatchRequest(BaseModel):
    display_name: str | None = None
    auto_connect: bool | None = None


class AccountUpsertResponse(BaseModel):
    ok: bool = True
    item: AccountRecord


class AccountDeleteResponse(BaseModel):
    ok: bool = True
    deleted: bool
