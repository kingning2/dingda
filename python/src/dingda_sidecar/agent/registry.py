"""Agent / Skill 注册表 — 委托 ``skills.registry``（含 AI 目录）。"""

from __future__ import annotations

from typing import Any

from dingda_sidecar.skills.registry import (
    ensure_builtin_skills,
    get_skill_spec,
    list_skill_specs,
    list_skills,
    make_skill_tools,
    skill_catalog_for_ai,
    skill_prompt_for_ai,
)
from dingda_sidecar.skills.spec import SkillSpec

ensure_builtin_skills()


def get_skill(skill_id: str) -> Any:
    """返回 skill 包模块（若已注册）；比价等工作流不在 skills 下。"""
    spec = get_skill_spec(skill_id)
    return __import__(f"skills.{spec.id}", fromlist=["*"])


__all__ = [
    "SkillSpec",
    "ensure_builtin_skills",
    "get_skill",
    "get_skill_spec",
    "list_skill_specs",
    "list_skills",
    "make_skill_tools",
    "skill_catalog_for_ai",
    "skill_prompt_for_ai",
]
