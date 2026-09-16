"""CLI 会话角色：这次会话「是谁在跑」的策略集合。

职责：
    定义父（编排）/ worker（选品）/ child（修复）三种角色的差异：提示词怎么拼、
    注入哪些 Skill、工作目录落哪、给 CLI 子进程塞哪些环境变量。

设计说明：
    - 角色不碰进程：resolve / spawn / 流解析 / 日志仍在 ``base.CliRuntime``
    - **拼装只在基类写一遍**：``compose_prompt`` 由基类按 ``uses_system_prompt`` /
      ``persona`` / ``skill_ids()`` 决定形状，角色不再各抄一份
    - 提示词正文在 ``prompts.PERSONAS``（按 ``persona`` 键取），本文件只存键名
    - 临时工作目录统一走 ``scratch_workdir(prefix)``：按角色前缀进程内复用一份，
      且一律不落仓库（cwd 在仓库 = 能顺手读到 extract.json / 源码，子 agent
      「自己推」就失去意义）

使用示例：
    role = get_role("worker")
    await runtime.run(prompt, role=role)
"""

from __future__ import annotations

import logging
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from cli.prompts import compose_role_prompt
from cli.skill import ORCHESTRATE_SKILL_NAMES, WORKER_SKILL_NAMES
from core.errors import AppError

logger = logging.getLogger("dingda.cli.roles")

_WORKDIRS: dict[str, Path] = {}

DEFAULT_ROLE = "parent"


def scratch_workdir(prefix: str) -> Path:
    """按前缀取一份临时工作目录，进程内只建一次。"""
    found = _WORKDIRS.get(prefix)
    if found is None:
        found = Path(tempfile.mkdtemp(prefix=prefix))
        _WORKDIRS[prefix] = found
    return found


class AgentRole(ABC):
    """会话角色插座：提示词 / Skill / 工作目录 / 环境。"""

    id: ClassVar[str]
    name: ClassVar[str]
    # 是否拼角色人设前言（child 只发本次 prompt）
    uses_system_prompt: ClassVar[bool] = True
    # prompts.PERSONAS 的键；None = 无人设
    persona: ClassVar[str | None] = None

    def compose_prompt(
        self,
        prompt: str,
        *,
        platform_hint: str | None = None,
        resume: bool = False,
        workdir: Path | None = None,
        context_messages: list | None = None,
    ) -> str:
        """拼最终写进 CLI stdin 的 prompt。

        不拼人设的角色（child）只发本次 prompt，避免前言把任务带偏。
        """
        if not self.uses_system_prompt:
            return f"{(prompt or '').strip()}\n"
        return compose_role_prompt(
            prompt,
            persona=self.persona or "",
            skill_ids=self.skill_ids(),
            platform_hint=platform_hint,
            resume=resume,
            workdir=workdir,
            context_messages=context_messages,
        )

    def run_env(self) -> dict[str, str]:
        """会话级追加环境；默认不加。"""
        return {}

    def skill_ids(self) -> tuple[str, ...]:
        """本角色注入哪些 Skill；空元组 = 不注入。"""
        return ()

    def session_env(self) -> dict[str, str]:
        """进 CLI 子进程的角色级环境。"""
        return {}

    @abstractmethod
    def workdir(self, cwd: str | None) -> Path:
        """这次会话的工作目录。"""


class ParentRole(AgentRole):
    """父 agent：主编排器，只派工 / 监督 / 调度修复。"""

    id = "parent"
    name = "父 agent"
    persona = "orchestrator"

    def skill_ids(self) -> tuple[str, ...]:
        """只注入编排 Skill。"""
        return ORCHESTRATE_SKILL_NAMES

    def session_env(self) -> dict[str, str]:
        """父会话标记。"""
        return {"DINGDA_AGENT_ROLE": "parent"}

    def workdir(self, cwd: str | None) -> Path:
        """系统临时目录，忽略调用方 cwd。"""
        return scratch_workdir("dingda-parent-agent-")


class WorkerRole(AgentRole):
    """worker：选品取证，可调 search / product / compare / login / preview。"""

    id = "worker"
    name = "worker"
    persona = "worker"

    def skill_ids(self) -> tuple[str, ...]:
        """选品 + 比价 Skills。"""
        return WORKER_SKILL_NAMES

    def session_env(self) -> dict[str, str]:
        """DOM 失效上抛给父进程，禁止 crawler 内联修复。"""
        return {
            "DINGDA_AGENT_ROLE": "worker",
            "DINGDA_REPAIR_OWNER": "parent",
        }

    def workdir(self, cwd: str | None) -> Path:
        """系统临时目录。"""
        return scratch_workdir("dingda-worker-agent-")


class ChildRole(AgentRole):
    """子 agent：单一职责、窄工具面、无父前言。

    工具面就是 prompt 里写死的那条 ``python -m tools.validate_cli`` 命令行，
    比任何工具白名单都窄；运行期才知道的值（如 ``DINGDA_VALIDATE_URL``）由调用方
    经 ``run_env`` 叠进 CLI 进程环境。
    """

    id = "child"
    name = "子 agent"
    uses_system_prompt = False

    def workdir(self, cwd: str | None) -> Path:
        """落在系统临时目录，忽略调用方给的 cwd。"""
        return scratch_workdir("dingda-child-agent-")


_ROLES: dict[str, AgentRole] = {
    role.id: role for role in (ParentRole(), WorkerRole(), ChildRole())
}


def get_role(role: str | AgentRole | None = None) -> AgentRole:
    """取角色：传对象原样返回，传名字查表，不传则默认父 agent。"""
    if isinstance(role, AgentRole):
        return role
    key = (role or DEFAULT_ROLE).strip().lower() or DEFAULT_ROLE
    found = _ROLES.get(key)
    if found is None:
        raise AppError("cli.role_unsupported", f"未知会话角色：{role}")
    return found


def list_role_ids() -> list[str]:
    """已实现角色的 id。"""
    return sorted(_ROLES)
