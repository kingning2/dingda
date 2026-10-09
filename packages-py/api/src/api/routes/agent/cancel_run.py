"""CLI 运行取消端点。

职责：
    取消 Python 侧正在跑的 CLI 子进程。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from cli.spawn import cancel_run
from core.errors import AppError

router = APIRouter()


@router.post("/runtimes/runs/{run_id}/cancel")
async def cancel_agent_runtime_run(run_id: str) -> dict[str, Any]:
    """取消 Python 侧正在跑的 CLI。"""
    key = run_id.strip()
    if not key:
        raise AppError("agent.run_invalid_id", "run_id 不能为空", status_code=400)
    await cancel_run(key)
    return {"ok": True, "run_id": key}
