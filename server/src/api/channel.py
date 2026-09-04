"""渠道扫码登录 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter

from src.contracts.channel import (
    QrCancelRequest,
    QrCancelResponse,
    QrCheckResponse,
    QrStartRequest,
    QrStartResponse,
)
from src.domains.channel.qr_service import get_channel_qr_service

router = APIRouter(prefix="/v1/channel", tags=["channel"])


@router.post("/qr/start", response_model=QrStartResponse)
def qr_start(request: QrStartRequest) -> QrStartResponse:
    return get_channel_qr_service().start(request)


@router.get("/qr/check", response_model=QrCheckResponse)
def qr_check(session_id: str) -> QrCheckResponse:
    return get_channel_qr_service().check(session_id)


@router.post("/qr/cancel", response_model=QrCancelResponse)
def qr_cancel(request: QrCancelRequest) -> QrCancelResponse:
    """关闭扫码弹窗时调用，打断后台浏览器任务。"""
    return get_channel_qr_service().cancel(request.session_id)
