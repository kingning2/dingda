"""账号 HTTP 路由（读/删 + 偏好 PATCH；登录态由扫码/探活侧写入）。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.contracts.account import (
    AccountDeleteResponse,
    AccountListResponse,
    AccountPatchRequest,
    AccountPlatform,
    AccountUpsertResponse,
)
from src.domains.account.service import get_account_service

router = APIRouter(prefix="/v1/accounts", tags=["accounts"])


@router.get("", response_model=AccountListResponse)
def list_accounts(
    platform: AccountPlatform | None = Query(default=None),
) -> AccountListResponse:
    return get_account_service().list(platform=platform)


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
