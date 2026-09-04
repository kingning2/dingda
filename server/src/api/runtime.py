"""运行时状态 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter

from src.domains.runtime import RuntimeService

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])
_runtime = RuntimeService()


@router.get("/status")
def runtime_status() -> dict[str, object]:
    """返回当前运行时快照。"""
    return _runtime.snapshot()
