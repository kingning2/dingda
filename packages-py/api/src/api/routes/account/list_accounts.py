"""账号列表端点。

职责：
    按平台过滤返回账号库中的账号列表。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from contracts.account import AccountListResponse, AccountPlatform
from domains.account.service import get_account_service

router = APIRouter(prefix="/v1/accounts")


@router.get("", response_model=AccountListResponse)
def list_accounts(
    platform: AccountPlatform | None = Query(default=None),
) -> AccountListResponse:
    """列出账号，可按平台过滤。"""
    return get_account_service().list(platform=platform)
