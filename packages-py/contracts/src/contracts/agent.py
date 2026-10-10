"""Agent API 契约模型。

职责：
    定义 Agent 相关 HTTP 接口的请求与响应结构，
    供 FastAPI 校验与前端 ``src/contracts`` 对齐。

设计说明：
    - AI 工作对话快照走 ``agent_works``（产品自建真相源）
    - Agent 运行入口在 ``/v1/agent/works/{id}/run``（内置 LLM + 工具循环）
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentWorkDetailResponse(BaseModel):
    """单条 AI 工作对话快照。"""

    ok: bool = True
    detail: dict[str, Any]


class AgentWorkSummaryView(BaseModel):
    """工作列表摘要（首页最近项目）。"""

    work_id: str
    title: str
    updated_at: float
    status_label: str | None = None
    status_state: str | None = None


class AgentWorkListResponse(BaseModel):
    """工作列表。"""

    ok: bool = True
    items: list[AgentWorkSummaryView] = Field(default_factory=list)


class AgentWorkPutRequest(BaseModel):
    """覆盖写入 AI 工作对话快照。"""

    detail: dict[str, Any]
