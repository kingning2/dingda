"""CLI 会话角色插座。

职责：
    定义「这次会话是谁在跑」的策略：提示词怎么拼、MCP 给不给（给哪些工具）、
    工作目录落哪。父 agent（选品调研）与子 agent（单一职责）的差异全收在这里。

设计说明：
    - 角色不碰进程：resolve / spawn / 流解析 / 日志仍在 ``base.CliRuntime``
    - ``mcp_env()`` 给会话级的 MCP 追加环境；调用方再叠上本次运行才有的值
      （如校验回打地址），角色负责的是「工具面有多大」这条策略
    - 加新角色（如「比价子 agent」）：本包加插头 + registry 登记一行

使用示例：
    role = get_role("child")
    await runtime.run(prompt, role=role)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger("dingda.cli.roles")


class AgentRole(ABC):
    """会话角色插座：提示词 / MCP / 工作目录。"""

    id: ClassVar[str]
    name: ClassVar[str]
    # 是否拼 system.md 选品前言（子 agent 只发本次 prompt）
    uses_system_prompt: ClassVar[bool] = True

    @abstractmethod
    def compose_prompt(
        self,
        prompt: str,
        *,
        platform_hint: str | None = None,
        resume: bool = False,
        workdir: Path | None = None,
        context_messages: list | None = None,
    ) -> str:
        """拼最终写进 CLI stdin 的 prompt。"""

    @abstractmethod
    def mcp_mode(self, runtime_mode: str) -> str:
        """工具注入模式；恒返回 ``"none"``（工具统一走 skill，不注入 MCP）。"""

    def mcp_env(self) -> dict[str, str]:
        """会话级 MCP 追加环境；默认不加。"""
        return {}

    @abstractmethod
    def workdir(self, cwd: str | None) -> Path:
        """这次会话的工作目录。"""
