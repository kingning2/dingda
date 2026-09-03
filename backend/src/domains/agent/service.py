"""Agent 领域服务。

职责：
    承载 AI Agent 的核心业务编排，包括：
    - LangGraph 工作流执行
    - 工具注册与调用（搜索、爬虫、知识检索等）
    - 流式事件推送到前端（经 infrastructure 事件总线）
    - 任务上下文与取消管理

迁移来源：
    旧版 ``dingda_sidecar.agent`` 与 ``dingda_sidecar.runtime.agent``

设计约定：
    - 不直接处理 HTTP，由 ``api/agent`` 调用本服务
    - 模型配置、Prompt 模板等可放在同目录子模块（待建）
    - 日志使用 ``logging.getLogger("dingda.agent")``
"""

from __future__ import annotations

import logging

logger = logging.getLogger("dingda.agent")


class AgentService:
    """Agent 应用服务：封装一次完整的 Agent 运行生命周期。"""

    # 从 dingda_sidecar.agent + runtime/agent 迁移实现
