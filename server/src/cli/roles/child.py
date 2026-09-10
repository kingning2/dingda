"""单一职责子 agent 角色。

职责：
    子 agent 只做一件事（如修 DOM 选择器）：只发本次 prompt、工作目录落在系统临时目录、
    工具面**窄**（只给声明的那一个校验工具），免掉递归与"顺手读到现成答案"。

设计说明：
    - 临时目录进程内复用一份（``_WORKDIR``），不每次新建
    - MCP 仍注入，但经 ``DINGDA_MCP_TOOLS`` 白名单只放 ``CHILD_TOOLS``；
      运行期才知道的值（如校验回打地址）由调用方经 ``mcp_env`` 叠上
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from src.cli.roles.base import AgentRole

logger = logging.getLogger("dingda.cli.roles.child")

# 子 agent 能用的工具：只放校验用的那一个
CHILD_TOOLS = "validate_selectors"

_WORKDIR: Path | None = None


def scratch_workdir() -> Path:
    """子 agent 的隔离工作目录：系统临时目录，不进仓库。

    它只该看收到的任务输入。若 cwd 落在仓库里，它就能顺手读到 ``extract.json`` /
    ``DOM_PROBE.md`` 里现成的选择器，「自己推」这件事就失去意义了。
    """
    global _WORKDIR
    if _WORKDIR is None:
        _WORKDIR = Path(tempfile.mkdtemp(prefix="dingda-child-agent-"))
    return _WORKDIR


class ChildRole(AgentRole):
    """子 agent：单一职责、窄工具面、无父前言。"""

    id = "child"
    name = "子 agent"
    uses_system_prompt = False

    def compose_prompt(
        self,
        prompt: str,
        *,
        platform_hint: str | None = None,
        resume: bool = False,
    ) -> str:
        """只发本次 prompt，不拼任何前言。"""
        return f"{(prompt or '').strip()}\n"

    def mcp_mode(self, runtime_mode: str) -> str:
        """照常注入 —— 工具面靠 ``mcp_env`` 的白名单收窄。"""
        return runtime_mode

    def mcp_env(self) -> dict[str, str]:
        """只放校验工具；另外把仓库根加进 PYTHONPATH。

        PYTHONPATH 是给「走 CLI 回打」那条退路用的：子 agent 的 cwd 是临时目录，
        没有它 ``python -m src.tools.validate_cli`` 找不到 `src`。
        """
        from src.cli.inject.mcp import server_dir

        return {
            "DINGDA_MCP_TOOLS": CHILD_TOOLS,
            "PYTHONPATH": str(server_dir()),
        }

    def workdir(self, cwd: str | None) -> Path:
        """落在系统临时目录，忽略调用方给的 cwd。"""
        return scratch_workdir()
