"""选品父 agent 角色。

职责：
    父 agent 带工具、带人设：拼 ``system.md`` 选品前言 + 平台提示，用 runtime 自己的
    MCP 注入模式，工作目录用调用方给的（默认进程 cwd）。
"""

from __future__ import annotations

from pathlib import Path

from src.cli.prompts import compose_agent_prompt
from src.cli.roles.base import AgentRole


class ParentRole(AgentRole):
    """父 agent：选品调研，可调 search / product / compare / login / preview。"""

    id = "parent"
    name = "父 agent"

    def compose_prompt(
        self,
        prompt: str,
        *,
        platform_hint: str | None = None,
        resume: bool = False,
    ) -> str:
        """系统前言 + 平台提示 + 用户原文；续聊只发原文。"""
        return compose_agent_prompt(prompt, platform_hint=platform_hint, resume=resume)

    def mcp_mode(self, runtime_mode: str) -> str:
        """不拦：用 runtime 自己声明的注入模式。"""
        return runtime_mode

    def workdir(self, cwd: str | None) -> Path:
        """调用方给的目录；没给就用进程 cwd。"""
        return Path(cwd).resolve() if cwd and cwd.strip() else Path.cwd()
