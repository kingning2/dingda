"""Agent / Skill 注册表 — 委托 ``skills.registry``（含 AI 目录）。"""

from __future__ import annotations

from typing import Any

from skills.registry import (
    ensure_builtin_skills,
    get_skill_spec,
    list_skill_specs,
    list_skills,
    make_skill_tools,
    skill_catalog_for_ai,
    skill_prompt_for_ai,
)
from skills.spec import SkillSpec

ensure_builtin_skills()


def get_skill(skill_id: str) -> Any:
    """返回 skill 包模块（含 lazy workflow 入口）。"""
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
