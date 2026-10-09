"""渠道扫码登录路由域。

职责：
    聚合 channel 域各端点挂到 ``/v1/channel``；每端点一个文件。
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.channel import qr_cancel, qr_check, qr_start

router = APIRouter(prefix="/v1/channel", tags=["channel"])
router.include_router(qr_start.router)
router.include_router(qr_check.router)
router.include_router(qr_cancel.router)
