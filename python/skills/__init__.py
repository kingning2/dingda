"""skills — Agent 可调用的业务技能包（AI 可见规格）。

不急加载 ``*.workflow``，避免与 runtime/tools 循环导入。
Builtin 规格经 ``skills.registry.ensure_builtin_skills`` 注册。
"""

from __future__ import annotations

from skills.registry import (
    ensure_builtin_skills,
    get_skill_spec,
    langchain_tools_for_skill,
    list_skill_specs,
    list_skills,
    make_skill_tools,
    skill_catalog_for_ai,
    skill_prompt_for_ai,
)
from skills.spec import SkillSpec, format_skill_for_ai

ensure_builtin_skills()

__all__ = [
    "SkillSpec",
    "ensure_builtin_skills",
    "format_skill_for_ai",
    "get_skill_spec",
    "langchain_tools_for_skill",
    "list_skill_specs",
    "list_skills",
    "make_skill_tools",
    "skill_catalog_for_ai",
    "skill_prompt_for_ai",
]
