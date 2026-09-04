"""进程内事件总线。

职责：
    提供轻量级的发布/订阅机制，将领域层产生的事件转发给：
    - WebSocket / SSE 推送层（推送到前端）
    - 日志、指标等观测组件

设计说明：
    - 当前为单进程内存实现，不跨进程、不持久化
    - ``publish(topic, payload)`` 的 topic 建议与契约事件名对齐
    - 订阅方在应用启动时注册 handler

使用示例（规划）：
    bus = EventBus()
    bus.subscribe(forward_to_websocket)
    bus.publish("agent/run/started", {"task_id": "..."})

后续可替换为 Redis/NATS 等，但桌面本地优先保持简单。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("dingda.events")

EventHandler = Callable[[str, dict[str, Any]], None]


class EventBus:
    """同步内存事件总线：主题 + JSON 可序列化 payload。"""

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        """注册事件处理器；同一 handler 可接收所有 topic。"""
        self._handlers.append(handler)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """向所有订阅者广播事件。"""
        for handler in self._handlers:
            handler(topic, payload)
