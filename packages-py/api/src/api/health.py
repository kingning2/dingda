"""健康检查 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter

from api.boot.warmup import current_phase

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """返回存活状态，供 Rust 壳层探活（不触发完整预热）。"""
    return {"status": "ok", "phase": current_phase()}
