"""Agent API 契约模型。

定义 Agent 相关 HTTP 接口的请求与响应结构。
用于 FastAPI 自动校验与 OpenAPI 文档生成。

当前模型：
    AgentPingRequest   探活/测试用请求体
    AgentPingResponse  探活/测试用响应体

后续扩展：
    AgentRunRequest、AgentRunEvent、AgentCancelRequest 等，
    与 ``contracts/schema/v1/agent`` 及 AG-UI 事件映射保持一致。
"""

from __future__ import annotations

from pydantic import BaseModel


class AgentPingRequest(BaseModel):
    """Agent 探活请求。"""

    message: str = "ping"


class AgentPingResponse(BaseModel):
    """Agent 探活响应。"""

    ok: bool = True
    echo: str
