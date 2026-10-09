"""SSE 事件帧格式化。

职责：
    把 ``(event, data)`` 收成 ``text/event-stream`` 的一帧字符串。
    agent 运行流与 crawler 直播流共用，避免各写一份 f-string。

使用示例：
    yield sse_frame("result", {"ok": True})
"""

from __future__ import annotations

import json
from typing import Any


def sse_frame(event: str, data: dict[str, Any]) -> str:
    """按 SSE 规范输出一帧；中文不转义，前端 JSON.parse 即得原文。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
