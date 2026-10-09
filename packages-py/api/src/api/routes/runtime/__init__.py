"""运行时状态路由域。

职责：
    聚合 runtime 域各端点挂到 ``/v1/runtime``；每端点一个文件。
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.runtime import status

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])
router.include_router(status.router)
