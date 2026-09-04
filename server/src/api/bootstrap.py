"""壳层首屏所需的轻量 bootstrap 接口。"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from src.core.warmup import current_phase, ensure_warmed
from src.domains.runtime import RuntimeService

router = APIRouter(prefix="/v1", tags=["bootstrap"])
_runtime = RuntimeService()


@router.get("/bootstrap")
def bootstrap(background_tasks: BackgroundTasks) -> dict[str, object]:
    """立即返回壳层快照，并在后台触发完整预热。"""
    background_tasks.add_task(ensure_warmed)
    return {
        "ok": True,
        "phase": current_phase(),
        "runtime": _runtime.snapshot(phase=current_phase()),
        "capabilities": ["health", "runtime", "bootstrap"],
    }
