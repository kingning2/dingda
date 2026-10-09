"""账号连接端点。

职责：
    把账号标记为「已连接」（产品开关，决定爬虫是否用它的 cookie）。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.account import AccountUpsertResponse
from domains.account.service import get_account_service

router = APIRouter(prefix="/v1/accounts")


@router.post("/{account_id}/connect", response_model=AccountUpsertResponse)
def connect_account(account_id: str) -> AccountUpsertResponse:
    """把账号标记为已连接。"""
    return get_account_service().connect(account_id)
