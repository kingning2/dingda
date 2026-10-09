"""账号主页快照端点。

职责：
    返回某账号的主页页快照（昵称、头像、探活结果等）。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.account import AccountProfileResponse
from domains.account.service import get_account_service

router = APIRouter(prefix="/v1/accounts")


@router.get("/{account_id}/profile", response_model=AccountProfileResponse)
def get_account_profile(account_id: str) -> AccountProfileResponse:
    """读取账号主页快照。"""
    return get_account_service().profile_page(account_id)
