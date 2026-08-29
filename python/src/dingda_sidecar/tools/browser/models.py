"""Browser tool 模型（会话/页面占位，实现逐步补）。"""

from __future__ import annotations

from typing import TypedDict


class BrowserStatus(TypedDict, total=False):
    available: bool
    engine: str
