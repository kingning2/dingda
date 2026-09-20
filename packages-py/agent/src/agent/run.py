"""Agent 运行入口：登录门禁 → 主编排。

职责：
    一整轮用户提问的程序侧骨架 —— 先确认登录态（失效就请用户扫码），
    再把问题交给主编排；返回退出码给接线方。

设计说明：
    - **登录门禁在主编排之前**：让模型去发现「没登录」要多绕好几轮，还可能编造数据
      充数。程序先查一次，失效直接请用户扫码，模型进来就能干活。
    - 三平台**同时**校验（``asyncio.gather`` + ``to_thread``），全部结束后一次性汇总，
      再对失效平台逐个扫码 —— 逐个等会把首屏时间拖成三倍。
    - 门禁之后的异常都收成退出码：SSE 流必须有个头尾，不能悬着。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from agent.context import AuthSnapshot, RunContext, emit_tool_call, emit_tool_result
from agent.loop import EXIT_CANCELLED, EXIT_FAILED, EXIT_OK
from agent.orchestrator import run_orchestrator
from agent.sse import EventBus
from agent.steps import platform_label
from agent.tools.login import login_blocking

logger = logging.getLogger("dingda.agent.run")

# 用户一句话进来后，程序同时校验的平台（与前端展示文案一致）。
AUTH_PLATFORMS = ("xiaohongshu", "xianyu", "ali1688")

__all__ = ["AUTH_PLATFORMS", "ensure_logins", "run_chat"]


async def run_chat(
    *,
    bus: EventBus,
    ctx: RunContext,
    prompt: str,
    platform_hint: str | None = None,
    context_messages: Sequence[Mapping[str, Any]] = (),
) -> int:
    """一整轮编排：门禁 → 主编排；返回 exitCode。"""
    try:
        await ensure_logins(bus, ctx=ctx)
        if ctx.cancelled():
            await bus.error("运行已取消")
            return EXIT_CANCELLED

        outcome = await run_orchestrator(
            ctx,
            prompt,
            platform_hint=platform_hint,
            context_messages=[dict(item) for item in context_messages],
        )
        return int(outcome.get("exit_code") or EXIT_OK)
    except Exception:  # noqa: BLE001 — 入口必须兜住，否则 SSE 流没有收尾帧
        logger.exception("编排意外异常 run=%s", ctx.run_id)
        await bus.error("运行出现意外错误，请重试")
        return EXIT_FAILED


async def ensure_logins(bus: EventBus, *, ctx: RunContext) -> None:
    """三平台同时校验；全部结束后一次性汇总（可多个失效）；再对失效平台逐个扫码。"""
    if ctx.cancelled():
        return

    checker = ctx.auth_checker
    if checker is None:
        logger.warning("未注入 auth_checker，跳过登录门禁 run=%s", ctx.run_id)
        return

    labels = [platform_label(platform) for platform in AUTH_PLATFORMS]
    await bus.text(f"正在同时校验{'、'.join(labels)}是否有效…")

    async def _one(platform: str) -> tuple[str, AuthSnapshot]:
        # 同步查询放到线程，三平台真正并行
        return platform, await asyncio.to_thread(checker, platform, None)

    results = await asyncio.gather(*(_one(platform) for platform in AUTH_PLATFORMS))
    if ctx.cancelled():
        return

    ok_notes: list[str] = []
    failed: list[str] = []
    for platform, snap in results:
        label = platform_label(platform)
        if snap.auth_valid:
            ok_notes.append(f"{label}有效（{snap.display_name}）" if snap.display_name else f"{label}有效")
        else:
            failed.append(platform)

    lines = ["校验完成："]
    if ok_notes:
        lines.append("有效：" + "、".join(ok_notes))
    lines.append("失效：" + "、".join(platform_label(p) for p in failed) if failed else "全部有效")
    await bus.text("\n".join(lines))

    if not failed:
        return

    await bus.text("以下平台需要扫码登录：" + "、".join(platform_label(p) for p in failed))
    for platform in failed:
        if ctx.cancelled():
            return
        await bus.text(f"请扫码登录{platform_label(platform)}").after(_login(ctx, platform))


async def _login(ctx: RunContext, platform: str) -> None:
    """调扫码登录：先发 login 步骤块，再推二维码，阻塞到用户扫完。"""
    logger.info("发起扫码登录 platform=%s run=%s", platform, ctx.run_id)
    call_id = ctx.new_call_id("login")
    label = f"扫码登录 · {platform_label(platform)}"
    await emit_tool_call(
        ctx,
        call_id=call_id,
        name="login",
        label=label,
        hint="用 App 扫码登录",
        browser=False,
        payload={"platform": platform},
        kind="login",
    )
    ctx.active_call_id = call_id
    try:
        output = await login_blocking(platform, ctx, step_id=call_id)
    finally:
        ctx.active_call_id = None
    await emit_tool_result(ctx, call_id=call_id, output=output)
    if not output.get("ok"):
        logger.warning(
            "扫码登录未成功 platform=%s code=%s",
            platform,
            output.get("error_code"),
        )
