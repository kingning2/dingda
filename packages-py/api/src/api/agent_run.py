"""Agent 运行 HTTP 接线：注入依赖 + 把运行事件编成 SSE。

职责：
    薄路由层。编排（登录门禁 / 主编排 / 子 agent）在 ``agent.run`` 与
    ``agent.orchestrator``；run 的生命周期与投递日志在 ``agent.runs``；
    本文件只建 ``RunContext``、注入 cookie/auth/login/llm，再把日志编成 SSE 帧。

设计说明：
    - **run 的寿命不等于这个 HTTP 请求的寿命**。生成器被断开只退订，run 继续在
      服务端跑；重进页面走 ``resume_run`` 从 ``agent.runs`` 的日志接回来。
      所以这里没有 ``_RUNNING`` —— 取消与在跑查询都归 ``manager``。
    - 工厂自己吃掉 ``AppError``：没有可用模型配置是「运行失败」而不是「请求失败」，
      要在流里说人话，并且照样收尾。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from agent.context import AuthSnapshot, RunContext
from agent.llm.client import LlmClient
from agent.llm.providers import get_provider, resolve_settings
from agent.loop import EXIT_FAILED
from agent.run import run_chat
from agent.runs import RunFactory, RunManager, RunRecord
from agent.sse import EventBus
from core.errors import AppError
from domains.channel.qr_service import get_channel_qr_service
from infrastructure.db import accounts as account_repo
from infrastructure.db import llm_credentials as credential_repo

logger = logging.getLogger("dingda.api.agent_run")

manager = RunManager()
"""进程内所有在跑的 run（含刚结束、还在 TTL 内的）。"""


class AgentRunRequest(BaseModel):
    """Agent 运行请求。"""

    prompt: str = Field(description="用户原文")
    run_id: str | None = None
    work_id: str | None = Field(
        default=None,
        description="这次运行属于哪条工作对话；客户端断线后靠它找回在跑的 run",
    )
    model_id: str | None = None
    platform_hint: str | None = Field(
        default=None,
        description="本轮优先平台：xianyu / xiaohongshu / ali1688",
    )
    context_messages: list[dict[str, Any]] | None = Field(
        default=None,
        description="冷启动时由叮答托管的先前对话 [{role, content}, ...]",
    )


def cancel_run(run_id: str) -> bool:
    """给正在跑的 run 发取消信号。"""
    return manager.cancel(run_id)


async def stream_run(
    *,
    run_id: str,
    runtime_id: str,
    request: AgentRunRequest,
) -> AsyncIterator[str]:
    """一次运行的 SSE 文本流：起手一个新 run，或接回同 id 已在跑的那条。"""
    record = manager.get(run_id)
    if record is None:
        record = manager.start(
            run_id=run_id,
            runtime_id=runtime_id,
            work_id=request.work_id,
            factory=_factory_for(request, run_id),
            seed_events=(
                {"type": "runStarted", "runId": run_id, "runtimeId": runtime_id},
            ),
        )
    async for frame in _frames(record, after=0):
        yield frame


async def resume_run(*, run_id: str, after: int = 0) -> AsyncIterator[str]:
    """接回一次运行：先重放 ``seq > after`` 的日志，再续上直播。

    查不到就空手而归（端点先查过 ``manager.get`` 才 404，这里是防「查到之后被回收」）。
    """
    record = manager.get(run_id)
    if record is None:
        return
    async for frame in _frames(record, after=after):
        yield frame


async def _frames(record: RunRecord, *, after: int) -> AsyncIterator[str]:
    """日志条目 → SSE 文本帧；``seq`` 落进 ``id:`` 行当重放游标。"""
    async for seq, event in manager.attach(record.run_id, after=after):
        yield record.bus.encode(event, seq=seq)


def _factory_for(request: AgentRunRequest, run_id: str) -> RunFactory:
    """把 API 侧的依赖（cookie / auth / login / llm）闭包进 run 的协程工厂。

    模型客户端在这里创建、在这里关闭：它的寿命跟着 run 走，不再跟着 HTTP 请求走。
    """

    async def factory(bus: EventBus, cancel: asyncio.Event) -> int:
        try:
            client = _client_for_run()
        except AppError as exc:
            logger.warning("运行未启动 run=%s code=%s", run_id, exc.code)
            await bus.put({"type": "error", "message": exc.message})
            return EXIT_FAILED

        ctx = RunContext(
            run_id=run_id,
            task_id=run_id,
            emit=bus.bind_emit(),
            live=True,
            cookie_resolver=_resolve_cookie,
            auth_checker=_check_auth,
            login_port=get_channel_qr_service(),
            llm=client,
            cancel=cancel,
        )
        try:
            return await run_chat(
                bus=bus,
                ctx=ctx,
                prompt=request.prompt,
                platform_hint=request.platform_hint,
                context_messages=request.context_messages or (),
            )
        finally:
            await client.aclose()

    return factory


def _client_for_run() -> LlmClient:
    """建本次运行要用的模型客户端。"""
    row = credential_repo.get_active_credential()
    if row is None:
        logger.info("没有使用中的模型凭据，回落到环境变量")
        return LlmClient.from_env()

    entry = get_provider(row.provider)
    logger.info("使用凭据 id=%s provider=%s model=%s", row.credential_id, row.provider, row.model)
    return LlmClient(
        resolve_settings(
            provider=row.provider,
            model=row.model,
            base_url=row.base_url or entry.base_url,
            api_key=row.api_key,
        )
    )


def _resolve_cookie(platform: str, account_id: str | None = None) -> str | None:
    """按平台取一个登录有效的账号 cookie。"""
    if account_id:
        row = account_repo.get_account(account_id)
        return row.cookie if row is not None and row.cookie.strip() else None
    key = (platform or "").strip().lower()
    for row in account_repo.list_accounts(platform=key):
        if row.cookie.strip() and row.auth_valid:
            return row.cookie
    logger.info("运行取不到有效 cookie platform=%s", key)
    return None


def _check_auth(platform: str, account_id: str | None = None) -> AuthSnapshot:
    """查账号库登录态，不扫码（注入给 Workflow）。"""
    if account_id:
        row = account_repo.get_account(account_id)
        if row is None:
            return AuthSnapshot(auth_valid=False, has_cookie=False)
        cookie = (row.cookie or "").strip()
        return AuthSnapshot(
            auth_valid=bool(row.auth_valid and cookie),
            has_cookie=bool(cookie),
            account_id=row.account_id,
            display_name=row.display_name or None,
        )
    key = (platform or "").strip().lower()
    best: AuthSnapshot | None = None
    for row in account_repo.list_accounts(platform=key):
        cookie = (row.cookie or "").strip()
        snap = AuthSnapshot(
            auth_valid=bool(row.auth_valid and cookie),
            has_cookie=bool(cookie),
            account_id=row.account_id,
            display_name=row.display_name or None,
        )
        if snap.auth_valid:
            return snap
        if best is None and snap.has_cookie:
            best = snap
    return best or AuthSnapshot(auth_valid=False, has_cookie=False)
