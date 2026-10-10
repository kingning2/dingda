"""Agent 域请求模型。

职责：
    agent 域各端点的请求体 Pydantic 模型；响应模型统一放 ``contracts.agent``。

设计说明：
    - 只放 HTTP 入参形状，不写业务；校验失败由全局异常处理兜底
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentWorkRunRequest(BaseModel):
    """产品 Agent 运行请求。"""

    prompt: str = Field(description="用户原文")
    run_id: str | None = None
