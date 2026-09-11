"""会话角色插座：父 / 子 agent 的三条策略（提示词 / MCP / cwd）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cli.roles.base import AgentRole
from src.cli.roles.child import ChildRole
from src.cli.roles.parent import ParentRole
from src.cli.roles.registry import get_role, list_role_ids
from src.shared.errors import AppError


def test_get_role_defaults_to_parent() -> None:
    assert isinstance(get_role(), ParentRole)
    assert isinstance(get_role(None), ParentRole)
    assert set(list_role_ids()) == {"parent", "child"}


def test_get_role_accepts_name_and_instance() -> None:
    assert isinstance(get_role("child"), ChildRole)
    assert isinstance(get_role("PARENT"), ParentRole)
    custom = ChildRole()
    assert get_role(custom) is custom


def test_get_role_unknown_raises() -> None:
    with pytest.raises(AppError) as exc:
        get_role("nope")
    assert exc.value.code == "cli.role_unsupported"


def test_roles_are_agent_role_sockets() -> None:
    assert isinstance(get_role("parent"), AgentRole)
    assert isinstance(get_role("child"), AgentRole)


def test_parent_role_keeps_system_prompt_and_tools(tmp_path: Path) -> None:
    role = ParentRole()
    text = role.compose_prompt("搜露营椅", platform_hint="xianyu")
    assert "用户请求" in text  # system.md 前言拼进来了
    assert "搜露营椅" in text
    assert role.mcp_mode("codex-mcp") == "codex-mcp"  # 不拦工具
    assert role.workdir(str(tmp_path)) == tmp_path.resolve()


def test_child_role_strips_prompt_but_keeps_narrow_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.cli.roles import child as child_mod

    monkeypatch.setattr(child_mod, "_WORKDIR", tmp_path / "scratch")
    role = ChildRole()
    text = role.compose_prompt("只发这一句", platform_hint="xianyu")
    assert text.strip() == "只发这一句"
    assert "用户请求" not in text  # 不拼父前言
    assert role.uses_system_prompt is False
    # MCP 照常注入，但工具面靠白名单收窄
    assert role.mcp_mode("codex-mcp") == "codex-mcp"
    assert role.mcp_env()["DINGDA_MCP_TOOLS"] == "validate_selectors"
    # cwd 忽略调用方给的，落隔离目录
    assert role.workdir("D:/Desktop/dingda/server") == tmp_path / "scratch"


def test_parent_role_has_no_extra_mcp_env() -> None:
    assert ParentRole().mcp_env() == {}
    assert ParentRole().uses_system_prompt is True
