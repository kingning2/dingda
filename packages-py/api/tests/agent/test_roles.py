"""会话角色插座：父 / worker / child。"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.roles import (
    AgentRole,
    ChildRole,
    ParentRole,
    WorkerRole,
    get_role,
    list_role_ids,
)
from cli.skill import ORCHESTRATE_SKILL_NAMES, WORKER_SKILL_NAMES
from core.errors import AppError


def test_get_role_defaults_to_parent() -> None:
    assert isinstance(get_role(), ParentRole)
    assert set(list_role_ids()) == {"parent", "worker", "child"}


def test_get_role_accepts_name_and_instance() -> None:
    assert isinstance(get_role("child"), ChildRole)
    assert isinstance(get_role("worker"), WorkerRole)
    assert isinstance(get_role("PARENT"), ParentRole)
    custom = ChildRole()
    assert get_role(custom) is custom


def test_get_role_unknown_raises() -> None:
    with pytest.raises(AppError) as exc:
        get_role("nope")
    assert exc.value.code == "cli.role_unsupported"


def test_roles_are_agent_role_sockets() -> None:
    assert isinstance(get_role("parent"), AgentRole)
    assert isinstance(get_role("worker"), AgentRole)
    assert isinstance(get_role("child"), AgentRole)


def test_parent_role_is_orchestrator_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    role = ParentRole()
    text = role.compose_prompt("帮我找露营椅")
    assert "用户请求" in text
    assert "帮我找露营椅" in text
    assert "编排器" in text
    assert "child_run" in text
    assert "dingda-crawl" not in text
    assert role.skill_ids() == ORCHESTRATE_SKILL_NAMES
    work = role.workdir(str(Path("D:/repo")))
    assert work == role.workdir(None)
    assert "dingda-parent-agent-" in work.name


def test_worker_role_has_crawl_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DINGDA_HEADROOM", "0")
    role = WorkerRole()
    text = role.compose_prompt("搜露营椅", platform_hint="xianyu")
    assert "用户请求" in text
    assert "思考过程必须全程中文" in text or "全程中文" in text
    assert "搜露营椅" in text
    assert "dingda-price-compare" in text
    assert "crawler.needs_repair" in text
    assert role.skill_ids() == WORKER_SKILL_NAMES
    assert role.session_env().get("DINGDA_REPAIR_OWNER") == "parent"


def test_child_role_strips_prompt() -> None:
    role = ChildRole()
    text = role.compose_prompt("只发这一句", platform_hint="xianyu")
    assert text.strip() == "只发这一句"
    assert "用户请求" not in text
    assert role.uses_system_prompt is False
    assert role.skill_ids() == ()
