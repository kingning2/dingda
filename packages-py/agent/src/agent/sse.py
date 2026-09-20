"""运行事件队列：agent 往里塞事件，API 侧编成 SSE 帧。

职责：
    给 agent 一个与传输无关的推送口（``text`` / ``error`` / ``put``），
    以及把事件字典编成 SSE 文本帧的 ``encode``。

设计说明：
    - 队列而不是回调列表：agent 在协程里跑、API 在生成器里 yield，
      中间必须有一层缓冲，否则快的那头会把慢的那头堵死。
    - ``close`` 投一个哨兵，迭代自然结束 —— 比让 API 侧猜「还有没有」可靠。
      唯一的消费者是 ``agent.runs.RunManager``：它抽干队列、编 seq、记日志再扇出。
    - ``EventEmit.after`` 只是让调用点看起来像同步推完再做下一件事
      （推「请扫码」再阻塞等扫码），本身不异步。

使用示例：
    bus = EventBus(run_id)
    await bus.text("正在校验登录态")
    await bus.text("请扫码登录闲鱼").after(login(ctx, "xianyu"))
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")

EmitFn = Callable[[dict[str, Any]], Awaitable[None] | None]


class EventBus:
    """一次运行的事件队列。"""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def emit(self, event: dict[str, Any]) -> "EventEmit":
        """入队一条事件（须含 ``type``），返回可 ``.after`` 的句柄。"""
        kind = str(event.get("type") or "").strip()
        if not kind:
            raise ValueError("事件必须带 type")
        self._queue.put_nowait({"runId": self.run_id, **event, "type": kind})
        return EventEmit(self)

    def text(self, message: str) -> "EventEmit":
        """推一条 ``textDelta``（自动补换行，时间线好分段）。"""
        text = message if message.endswith("\n") else f"{message}\n"
        return self.emit({"type": "textDelta", "text": text})

    def error(self, message: str) -> "EventEmit":
        """推一条 ``error``。"""
        return self.emit({"type": "error", "message": message})

    async def put(self, event: dict[str, Any]) -> None:
        """给 ``RunContext.emit`` 用：工具推来的事件进同一条队列。"""
        kind = str(event.get("type") or "message")
        await self._queue.put({"runId": self.run_id, **event, "type": kind})

    def bind_emit(self) -> EmitFn:
        """返回可注入 ``RunContext.emit`` 的异步回调。"""

        async def _emit(event: dict[str, Any]) -> None:
            await self.put(event)

        return _emit

    async def close(self) -> None:
        """结束迭代（哨兵）。"""
        await self._queue.put(None)

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    def encode(self, event: dict[str, Any], *, seq: int | None = None) -> str:
        """事件字典 → SSE 文本帧。

        ``seq`` 写进 ``id:`` 行（见 ``agent.runs``）：它既是断线重连的游标
        （``?after=`` 用同一套编号），也是将来接 AG-UI 时 ``Last-Event-ID`` 的载体。
        不给就只发 ``event:`` / ``data:``，与从前逐字一致。
        """
        kind = str(event.get("type") or "message")
        head = f"id: {seq}\n" if seq is not None else ""
        return f"{head}event: {kind}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


class EventEmit:
    """刚入队的一条事件；可 ``await``，也可 ``.after(coro)`` 接着跑。"""

    __slots__ = ("_bus",)

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def __await__(self):
        """``await bus.text(...)`` —— 事件已入队，此处无额外工作。"""

        async def _done() -> None:
            return None

        return _done().__await__()

    def after(self, awaitable: Awaitable[T]) -> Awaitable[T]:
        """事件已推给前端，再执行 ``awaitable``（例如扫码登录）。"""
        return awaitable


# 兼容旧名（API 与测试仍在用）
SseBus = EventBus
SseEmit = EventEmit
