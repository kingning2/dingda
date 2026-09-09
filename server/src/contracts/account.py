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


class AccountProfileView(BaseModel):
    """个人主页摘要：扫码时已存的名称头像。"""

    account_id: str
    platform: AccountPlatform
    display_name: str
    avatar_url: str | None = None
    followers: int | None = None
    following: int | None = None
    sold_count: int | None = None
    purchase_count: int | None = None
    collection_count: int | None = None


class AccountProfileResponse(BaseModel):
    ok: bool = True
    profile: AccountProfileView


class BrowserCookieItem(BaseModel):
    """可注入 WebView 的单条 Cookie（含平台域名映射）。"""

    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = True
    http_only: bool = False
    same_site: str = "Lax"
    expires: float | None = None


class BrowserSessionResponse(BaseModel):
    """桌面商品预览用：cookie + localStorage。"""

    ok: bool = True
    platform: AccountPlatform
    account_id: str | None = None
    cookies: list[BrowserCookieItem] = Field(default_factory=list)
    local_storage: dict[str, str] = Field(default_factory=dict)
    message: str | None = None
