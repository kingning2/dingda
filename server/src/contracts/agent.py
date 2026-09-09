"""Agent API 契约模型。

职责：
    定义 Agent 相关 HTTP 接口的请求与响应结构，
    供 FastAPI 校验与前端 ``src/contracts`` 对齐。

设计说明：
    - 默认 Agent / 默认模型偏好走 SQLite ``app_settings``
    - AI 工作对话快照走 ``agent_works``（产品自建真相源）
    - CLI 探测仍由 Tauri 负责
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentPingRequest(BaseModel):
    """Agent 探活请求。"""

    message: str = "ping"


class AgentPingResponse(BaseModel):
    """Agent 探活响应。"""

    ok: bool = True
    echo: str


class AgentDefaultView(BaseModel):
    """当前默认外部 Agent CLI。"""

    ok: bool = True
    default_agent_id: str | None = None


class AgentDefaultPutRequest(BaseModel):
    """设置默认 Agent。"""

    agent_id: str = Field(min_length=1)


class AgentPreferencesView(BaseModel):
    """Agent 偏好快照（默认引擎 + 各引擎默认模型）。"""

    ok: bool = True
    default_agent_id: str | None = None
    default_models: dict[str, str] = Field(default_factory=dict)


class AgentDefaultModelPutRequest(BaseModel):
    """设置某 Agent 的默认模型。"""

    agent_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)


class AgentDefaultModelView(BaseModel):
    """写入默认模型后的回执。"""

    ok: bool = True
    agent_id: str
    model_id: str
    default_models: dict[str, str] = Field(default_factory=dict)


class AgentRuntimesCatalogView(BaseModel):
    """上次扫描落库的 Agent CLI 目录（含模型列表）。"""

    ok: bool = True
    agents: list[dict[str, Any]] = Field(default_factory=list)


class AgentRuntimesCatalogPutRequest(BaseModel):
    """覆盖写入 Agent CLI 扫描结果。"""

    agents: list[dict[str, Any]] = Field(default_factory=list)


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
