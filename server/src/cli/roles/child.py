"""单一职责子 agent 角色。

职责：
    子 agent 只做一件事（如修 DOM 选择器）：只发本次 prompt、工作目录落在系统临时目录、
    工具面**窄**（只走命令行回打，不注入任何工具总线），免掉递归与"顺手读到现成答案"。

设计说明：
    - 临时目录进程内复用一份（``_WORKDIR``），不每次新建
    - **不注入 MCP**：注入方式已统一为 skill；子 agent 的工具面就是 prompt 里
      写死的那条 ``python -m src.tools.validate_cli`` 命令行，反而更窄
    - 运行期才知道的值（如校验回打地址 ``DINGDA_VALIDATE_URL``）由调用方经
      ``mcp_env`` 叠上，直接进 CLI 进程环境
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from src.cli.roles.base import AgentRole

logger = logging.getLogger("dingda.cli.roles.child")

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
        workdir: Path | None = None,
        context_messages: list | None = None,
    ) -> str:
        """只发本次 prompt，不拼任何前言。"""
        return f"{(prompt or '').strip()}\n"

    def mcp_mode(self, runtime_mode: str) -> str:
        """不注入工具总线 —— 子 agent 的工具面收成 prompt 里那一条校验命令。"""
        return "none"

    def mcp_env(self) -> dict[str, str]:
        """把仓库根加进 PYTHONPATH，给「走 CLI 回打」用。

        子 agent 的 cwd 是临时目录，没有它 ``python -m src.tools.validate_cli``
        找不到 ``src``。
        """
        from src.cli.inject.mcp import server_dir

        return {
            "PYTHONPATH": str(server_dir()),
        }

    def workdir(self, cwd: str | None) -> Path:
        """落在系统临时目录，忽略调用方给的 cwd。"""
        return scratch_workdir()
