"""扫码进度轮询端点。

职责：
    按 session_id 返回扫码登录当前进度（等待/已扫/成功/失败）。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.channel import QrCheckResponse
from domains.channel.qr_service import get_channel_qr_service

router = APIRouter()


@router.get("/qr/check", response_model=QrCheckResponse)
def qr_check(session_id: str) -> QrCheckResponse:
    """轮询一次扫码进度。"""
    return get_channel_qr_service().check(session_id)
