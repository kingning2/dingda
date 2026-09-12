"""账号 HTTP 路由（读/删 + 偏好 PATCH；登录态由扫码/探活侧写入）。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from contracts.account import (
    AccountDeleteResponse,
    AccountListResponse,
    AccountPatchRequest,
    AccountPlatform,
    AccountProfileResponse,
    AccountUpsertResponse,
    BrowserCookieItem,
    BrowserSessionResponse,
)
from tools.account_cookie import resolve_browser_session
from domains.account.service import get_account_service

logger = logging.getLogger("dingda.api.account")

router = APIRouter(prefix="/v1/accounts", tags=["accounts"])


@router.get("", response_model=AccountListResponse)
def list_accounts(
    platform: AccountPlatform | None = Query(default=None),
) -> AccountListResponse:
    return get_account_service().list(platform=platform)


@router.get("/browser-session", response_model=BrowserSessionResponse)
def get_browser_session(
    platform: AccountPlatform = Query(..., description="xianyu / xiaohongshu"),
) -> BrowserSessionResponse:
    """商品预览注入用：返回已映射域名的 cookie 与 localStorage。"""
    session = resolve_browser_session(platform)
    if session is None:
        logger.info("browser-session empty platform=%s", platform)
        return BrowserSessionResponse(
            ok=False,
            platform=platform,
            message="未找到可用登录账号，将以未登录态打开",
        )
    cookies = [
        BrowserCookieItem(
            name=item.name,
            value=item.value,
            domain=item.domain,
            path=item.path or "/",
            secure=bool(item.secure),
            http_only=bool(item.http_only),
            same_site=item.same_site or "Lax",
            expires=float(item.expires) if item.expires is not None else None,
        )
        for item in session.cookies
    ]
    logger.info(
        "browser-session ok platform=%s account=%s cookies=%s ls=%s",
        platform,
        session.account_id,
        len(cookies),
        len(session.local_storage),
    )
    return BrowserSessionResponse(
        ok=True,
        platform=platform,  # type: ignore[arg-type]
        account_id=session.account_id,
        cookies=cookies,
        local_storage=session.local_storage,
    )


@router.get("/{account_id}/profile", response_model=AccountProfileResponse)
def get_account_profile(account_id: str) -> AccountProfileResponse:
    return get_account_service().profile_page(account_id)


@router.patch("/{account_id}", response_model=AccountUpsertResponse)
def patch_account(account_id: str, request: AccountPatchRequest) -> AccountUpsertResponse:
    return get_account_service().patch(account_id, request)


@router.post("/{account_id}/connect", response_model=AccountUpsertResponse)
def connect_account(account_id: str) -> AccountUpsertResponse:
    return get_account_service().connect(account_id)


@router.post("/{account_id}/disconnect", response_model=AccountUpsertResponse)
def disconnect_account(account_id: str) -> AccountUpsertResponse:
    return get_account_service().disconnect(account_id)


@router.delete("/{account_id}", response_model=AccountDeleteResponse)
def delete_account(account_id: str) -> AccountDeleteResponse:
    return get_account_service().delete(account_id)
