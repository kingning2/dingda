"""Agent 路由域。

职责：
    聚合 agent 域各端点挂到 ``/v1/agent``；每端点一个文件。
    覆盖默认 Agent / 默认模型偏好、CLI 目录缓存、AI 工作对话快照，
    以及产品 Agent / 外部 CLI 的 SSE 运行入口。

设计说明：
    - 偏好与扫描目录落在 SQLite ``app_settings``；对话快照落在 ``agent_works``
    - CLI 启动在 Python ``cli``，不再经 Tauri spawn；运行一律走本域
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.agent import (
    cancel_run,
    get_default,
    get_preferences,
    get_runtimes,
    get_work,
    list_works,
    post_live_frame,
    put_default,
    put_default_model,
    put_runtimes,
    put_work,
    run_runtime,
    run_work,
)

router = APIRouter(prefix="/v1/agent", tags=["agent"])
router.include_router(get_preferences.router)
router.include_router(get_default.router)
router.include_router(put_default.router)
router.include_router(put_default_model.router)
router.include_router(get_runtimes.router)
router.include_router(put_runtimes.router)
router.include_router(list_works.router)
router.include_router(get_work.router)
router.include_router(put_work.router)
router.include_router(run_work.router)
router.include_router(run_runtime.router)
router.include_router(post_live_frame.router)
router.include_router(cancel_run.router)
