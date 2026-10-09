"""运行时快照端点。

职责：
    返回当前 RuntimeService 快照，供壳层与设置页读取。
"""

from __future__ import annotations

from fastapi import APIRouter

from domains.runtime import RuntimeService

router = APIRouter()
_runtime = RuntimeService()


@router.get("/status")
def runtime_status() -> dict[str, object]:
    """返回当前运行时快照。"""
    return _runtime.snapshot()
