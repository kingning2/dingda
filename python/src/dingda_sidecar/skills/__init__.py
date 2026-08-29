"""skills — Agent 可调用的业务技能包（AI 可见规格）。

公用能力（web_fetch 等）注册在 ``tools.registry``；比价长流程在
``agent.workflows``，由程序调用，不作为 AI skill。
Builtin 规格经 ``skills.registry.ensure_builtin_skills`` 注册。
"""

from __future__ import annotations

from dingda_sidecar.skills.registry import (
    ensure_builtin_skills,
    get_skill_spec,
    langchain_tools_for_skill,
    list_skill_specs,
    list_skills,
    make_skill_tools,
    skill_catalog_for_ai,
    skill_prompt_for_ai,
)
from dingda_sidecar.skills.spec import SkillSpec, format_skill_for_ai

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
