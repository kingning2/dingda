"""会话角色注册表。

职责：
    按名取角色插头，避免调用方写 ``if role == "child"``。
"""

from __future__ import annotations

from src.cli.roles.base import AgentRole
from src.cli.roles.child import ChildRole
from src.cli.roles.parent import ParentRole
from src.shared.errors import AppError

_ROLES: dict[str, AgentRole] = {role.id: role for role in (ParentRole(), ChildRole())}

DEFAULT_ROLE = "parent"


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
