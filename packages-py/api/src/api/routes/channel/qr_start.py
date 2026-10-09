"""扫码登录发起端点。

职责：
    为指定平台拉起扫码登录后台任务，返回 session_id 供前端轮询。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.channel import QrStartRequest, QrStartResponse
from domains.channel.qr_service import get_channel_qr_service

router = APIRouter()


@router.post("/qr/start", response_model=QrStartResponse)
def qr_start(request: QrStartRequest) -> QrStartResponse:
    """拉起平台扫码登录任务。"""
    return get_channel_qr_service().start(request)
