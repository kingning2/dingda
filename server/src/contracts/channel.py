"""Channel / 扫码登录契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AccountPlatform = Literal["xianyu", "ali1688", "xiaohongshu"]


class QrStartRequest(BaseModel):
    platform: AccountPlatform


class QrStartResponse(BaseModel):
    ok: bool
    status: str
    session_id: str | None = None
    qr_base64: str | None = None
    qr_url: str | None = None
    detail: str | None = None


class QrCheckResponse(BaseModel):
    ok: bool
    status: str
    session_id: str | None = None
    qr_base64: str | None = None
    qr_url: str | None = None
    detail: str | None = None
    account_id: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    cookie: str | None = None

    model_config = {"populate_by_name": True}


class QrCheckQuery(BaseModel):
    session_id: str = Field(min_length=1)


class QrCancelRequest(BaseModel):
    session_id: str = Field(min_length=1)


class QrCancelResponse(BaseModel):
    ok: bool
    session_id: str
    detail: str | None = None

