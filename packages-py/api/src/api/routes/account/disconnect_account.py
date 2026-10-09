"""账号断开端点。

职责：
    取消账号的「已连接」开关，爬虫不再使用它的 cookie。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.account import AccountUpsertResponse
from domains.account.service import get_account_service

router = APIRouter(prefix="/v1/accounts")


@router.post("/{account_id}/disconnect", response_model=AccountUpsertResponse)
def disconnect_account(account_id: str) -> AccountUpsertResponse:
    """取消账号的已连接开关。"""
    return get_account_service().disconnect(account_id)
