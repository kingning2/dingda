"""Agent 域请求模型。

职责：
    agent 域各端点的请求体 Pydantic 模型；响应模型统一放 ``contracts.agent``。

设计说明：
    - 只放 HTTP 入参形状，不写业务；校验失败由全局异常处理兜底
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentWorkRunRequest(BaseModel):
    """产品 Agent 运行请求。"""

    prompt: str = Field(description="用户原文")
    run_id: str | None = None


class AgentRuntimeRunRequest(BaseModel):
    """外部 CLI Runtime 运行请求。"""

    prompt: str
    cwd: str | None = None
    model_id: str | None = None
    session_id: str | None = None
    reasoning: str | None = Field(
        default=None,
        description="推理强度 / OpenCode variant（可选）",
    )
    executable: str | None = Field(
        default=None,
        description="Tauri 扫描到的 CLI 绝对路径（优先于 PATH 再解析）",
    )
    extra_allowed_dirs: list[str] | None = None
    run_id: str | None = None
    platform_hint: str | None = Field(
        default=None,
        description="本轮优先平台：xianyu / xiaohongshu / ali1688",
    )
    context_messages: list[dict[str, Any]] | None = Field(
        default=None,
        description="换 Agent 冷启动时由叮答托管的先前对话 [{role, content}, ...]",
    )


class AgentLiveFrameRequest(BaseModel):
    """MCP preview 投递的一帧截图。"""

    url: str = ""
    title: str = ""
    hint: str | None = None
    mime: str = "image/jpeg"
    image_b64: str
