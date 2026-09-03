"""Agent 领域包导出。

对外统一导出 ``AgentService``，供 ``api/agent`` 路由及其他模块调用。
"""

from src.domains.agent.service import AgentService

__all__ = ["AgentService"]
