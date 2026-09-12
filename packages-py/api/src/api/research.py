"""Research HTTP 路由（骨架）。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/v1/research", tags=["research"])
