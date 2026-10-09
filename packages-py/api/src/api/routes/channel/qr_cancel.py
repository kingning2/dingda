"""扫码登录取消端点。

职责：
    关闭扫码弹窗时调用，打断后台浏览器任务。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.channel import QrCancelRequest, QrCancelResponse
from domains.channel.qr_service import get_channel_qr_service

router = APIRouter()


@router.post("/qr/cancel", response_model=QrCancelResponse)
def qr_cancel(request: QrCancelRequest) -> QrCancelResponse:
    """关闭扫码弹窗时调用，打断后台浏览器任务。"""
    return get_channel_qr_service().cancel(request.session_id)
