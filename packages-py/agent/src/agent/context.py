"""一次运行的上下文：agent 能用什么、事件往哪发。

职责：
    定义 ``RunContext`` —— 一次运行共享的可变环境（事件出口、直播开关、cookie、
    登录口、取消信号），以及 ``emit`` 系列助手（工具调用 / 直播帧 / 文本）。

设计说明：
    - 登录态与扫码都是**注入口**：agent 包不读 sqlite、不认 channels/infrastructure，
      账号库查询与扫码实现由接线方（api 层）给进来。
    - 取消是一个 ``asyncio.Event``，由接线方置位；各循环在**步与步之间**自查，
      跑了一半的工具不会被硬打断 —— 硬断会留下「执行中」的步骤块。
    - 事件形状手工对齐 ``packages/contracts/src/agent-event.ts``（契约没有 Python
      镜像），改字段名前端就会少一块。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from contracts.channel import (
    QrCancelResponse,
    QrCheckResponse,
    QrStartRequest,
    QrStartResponse,
)

from agent.steps import page_from_live_frame, step_for_call, step_for_result

logger = logging.getLogger("dingda.agent.context")

# 事件出口：由接线方注入；返回 None 表示同步回调，同样接受。
EmitFn = Callable[[dict[str, Any]], Awaitable[None] | None]

# Cookie 解析：显式 cookie 拿不到时，由接线方注入账号库查询。
CookieResolver = Callable[[str, str | None], str | None]


@dataclass(frozen=True, slots=True)
class AuthSnapshot:
    """一次登录态查询结果（不扫码）。"""

    auth_valid: bool
    has_cookie: bool
    account_id: str | None = None
    display_name: str | None = None


# 登录态查询：接线方注入；agent 不读 sqlite。
AuthChecker = Callable[[str, str | None], AuthSnapshot]


class LoginPort(Protocol):
    """扫码登录口子：接线方注入，实现走 ``domains.channel.qr_service``。

    抄的是 ``ChannelQrService`` 的三个同步方法：``start`` 起一次扫码会话并等出二维码，
    ``check`` 查一次状态（**登录成功时它自己把 cookie 落库**，实现方负责），
    ``cancel`` 丢掉会话让后台扫码让出浏览器。

    方法是同步的 —— 实现方在同步浏览器线程上跑，调用侧用 ``asyncio.to_thread`` 包。
    """

    def start(self, request: QrStartRequest) -> QrStartResponse: ...

    def check(self, session_id: str) -> QrCheckResponse: ...

    def cancel(self, session_id: str) -> QrCancelResponse: ...


@dataclass
class RunContext:
    """一次运行的可变环境；工具与各层 agent 都只认它。"""

    run_id: str
    task_id: str
    emit: EmitFn | None = None
    live: bool = False
    cookie_resolver: CookieResolver | None = None
    auth_checker: AuthChecker | None = None
    login_port: LoginPort | None = None
    llm: Any = None
    """本次运行的 ``LlmClient``；子 agent 复用同一把。"""
    cancel: Any | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    active_call_id: str | None = None
    """当前正在执行的工具步骤 id；扫码帧靠它钉到对应 login 块上。"""

    @property
    def live_enabled(self) -> bool:
        """本会话是否真的会推直播帧：开关打开且有人接。"""
        return self.live and self.emit is not None

    def cookie_for(self, platform: str) -> str | None:
        """取本平台 cookie：显式入参优先，其次问注入的解析器；都没有就 None。"""
        return self.refresh_cookie(platform)

    def refresh_cookie(self, platform: str) -> str | None:
        """问一次账号库要 cookie。"""
        if self.cookie_resolver is None:
            return None
        resolved = self.cookie_resolver(platform, None)
        return (resolved or "").strip() or None

    def cancelled(self) -> bool:
        """取消信号是否已被置位；没注入就算没取消。"""
        is_set = getattr(self.cancel, "is_set", None)
        return bool(callable(is_set) and is_set())

    async def emit_event(self, event: dict[str, Any]) -> None:
        """发一个事件；没接出口就丢掉（单测与离线跑工具时是常态）。"""
        if self.emit is None:
            return
        result = self.emit(event)
        if isinstance(result, Awaitable):
            await result

    async def emit_text(self, message: str) -> None:
        """推一段给用户的正文（自动补换行，时间线好分段）。"""
        text = message if message.endswith("\n") else f"{message}\n"
        await self.emit_event({"type": "textDelta", "text": text})

    async def emit_frame(
        self,
        *,
        url: str,
        title: str,
        hint: str | None,
        mime: str,
        image_b64: str,
        step_id: str | None = None,
    ) -> None:
        """把 crawler 的一帧截图转成前端认识的 ``browserFrame`` 事件并发出。

        用 data URL 而不是推给服务端：老的 ``/live-frame`` HTTP 端点已删除，
        现在工具与 SSE 在同一进程里，绕一圈 HTTP 只会多一个失败点。

        ``step_id`` 指定这帧落在哪个步骤块上。默认回落到 ``active_call_id``，
        再没有才让前端挂到当前进行中的 ``browser_crawl``。掉线恢复时必须显式填：
        那时搜索步骤还在跑，二维码会被它抢走。
        """
        if not image_b64:
            return
        screenshot_url = f"data:{mime or 'image/jpeg'};base64,{image_b64}"
        event: dict[str, Any] = {
            "type": "browserFrame",
            "url": url,
            "title": title,
            "hint": hint,
            "screenshot_url": screenshot_url,
            "page": page_from_live_frame(
                url=url,
                title=title,
                hint=hint,
                screenshot_url=screenshot_url,
            ),
        }
        target = step_id or self.active_call_id
        if target:
            event["stepId"] = target
        await self.emit_event(event)

    def new_call_id(self, prefix: str) -> str:
        """一次调用的步骤 id；同一次运行内不与其它调用撞车。"""
        return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def emit_tool_call(
    ctx: RunContext,
    *,
    call_id: str,
    name: str,
    label: str,
    hint: str | None,
    browser: bool,
    payload: dict[str, Any],
    kind: str | None = None,
) -> None:
    """发 ``toolCall``：前端据此建（或更新）一个步骤块。

    ``browser`` 为真时步骤块挂页卡（``kind = browser_crawl``）；
    扫码登录传 ``kind=\"login\"``，前端挂扫码块而不是直播页卡。
    """
    await ctx.emit_event(
        {
            "type": "toolCall",
            "id": call_id,
            "name": name,
            "input": payload,
            "step": step_for_call(
                call_id, label=label, hint=hint, browser=browser, kind=kind
            ),
        }
    )


async def emit_tool_result(ctx: RunContext, *, call_id: str, output: dict[str, Any]) -> None:
    """发 ``toolResult``：给步骤块收尾，出参全文落进折叠区（不截断）。"""
    await ctx.emit_event(
        {
            "type": "toolResult",
            "id": call_id,
            "output": output,
            "step": step_for_result(call_id, output),
        }
    )
