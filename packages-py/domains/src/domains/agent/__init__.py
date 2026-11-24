"""domains/agent：产品 Agent 应用服务（原 packages-py/agent/core 下收至此）。

职责：
    AgentService —— 收用户目标 → 经 Tool Registry 选型调用 → Headroom 压缩后
    调 LLM → 产出事件（供 api/routes/agent 的 SSE）。
    禁止直连 Playwright / Crawler Source / 平台 Channel。
"""

from __future__ import annotations

from domains.agent.service import AgentService

__all__ = ["AgentService"]
