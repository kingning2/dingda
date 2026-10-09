"""账号偏好修改端点。

职责：
    PATCH 某账号的偏好设置（轮询开关等）。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.account import AccountPatchRequest, AccountUpsertResponse
from domains.account.service import get_account_service

router = APIRouter(prefix="/v1/accounts")


@router.patch("/{account_id}", response_model=AccountUpsertResponse)
def patch_account(account_id: str, request: AccountPatchRequest) -> AccountUpsertResponse:
    """修改账号偏好设置。"""
    return get_account_service().patch(account_id, request)
