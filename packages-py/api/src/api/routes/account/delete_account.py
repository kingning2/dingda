"""账号删除端点。

职责：
    从账号库彻底删除账号及其 cookie。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.account import AccountDeleteResponse
from domains.account.service import get_account_service

router = APIRouter(prefix="/v1/accounts")


@router.delete("/{account_id}", response_model=AccountDeleteResponse)
def delete_account(account_id: str) -> AccountDeleteResponse:
    """删除账号。"""
    return get_account_service().delete(account_id)
