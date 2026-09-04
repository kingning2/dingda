"""产品 Agent 核心编排（骨架）。

职责：
    - LangGraph / 执行循环
    - 经 Tool Registry 选型调用（禁止直连 Playwright / Crawler Source）
    - 流式事件经 infrastructure 事件总线推送

由 ``api/agent`` 调用；实现落在 ``agent/core`` 与 ``agent/workflows``。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dingda.agent")


class AgentService:
    """Agent 运行生命周期入口（骨架，待接 Tool Registry）。"""
