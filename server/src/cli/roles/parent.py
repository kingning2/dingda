"""选品父 agent 角色。

职责：
    父 agent 带工具、带人设：拼 ``system.md`` 选品前言 + 平台提示。
    工具**统一以 skill 形式注入**（runtime 读 skills 目录里的 ``dingda-crawl/SKILL.md``），
    不再注入 MCP；工作目录用调用方给的（默认进程 cwd）。
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
        """工具统一走 skill：不给任何 runtime 注入 MCP。

        ``runtime_mode`` 仍旧接住（接口形状不变），但恒返回 ``"none"``——
        与 ``ChildRole`` 一致，工具只从 ``dingda-crawl`` skill 的 SKILL.md 得到。
        """
        return "none"

    def workdir(self, cwd: str | None) -> Path:
        """调用方给的目录；没给就用进程 cwd。"""
        return Path(cwd).resolve() if cwd and cwd.strip() else Path.cwd()
