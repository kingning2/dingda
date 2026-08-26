"""Skill 注册表 — AI 可见规格 + 工具绑定 + 可 bind 的 skill 工具。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from skills.spec import SkillSpec, format_skill_for_ai
from tools.registry import bind_skill_tools, format_tools_for_ai, tools_for_skill

_SPECS: dict[str, SkillSpec] = {}
_BUILTINS_LOADED = False


def register_skill(spec: SkillSpec) -> None:
    sid = spec.id.strip()
    if not sid:
        raise ValueError("skill id 为空")
    if not spec.name.strip():
        raise ValueError(f"skill={sid} 缺少 name")
    if not spec.description.strip():
        raise ValueError(f"skill={sid} 缺少 AI description")
    if not getattr(spec, "parameters", None):
        raise ValueError(f"skill={sid} 缺少 parameters schema")
    bind_skill_tools(sid, spec.tools)
    _SPECS[sid] = spec


def get_skill_spec(skill_id: str) -> SkillSpec:
    ensure_builtin_skills()
    spec = _SPECS.get(skill_id.strip())
    if spec is None:
        raise KeyError(f"unknown skill: {skill_id}")
    return spec


def list_skills() -> list[str]:
    ensure_builtin_skills()
    return sorted(_SPECS)


def list_skill_specs() -> list[SkillSpec]:
    return [_SPECS[k] for k in list_skills()]


def skill_catalog_for_ai() -> str:
    """全部 skill 的 AI 目录（描述 + 参数 + 每个工具的参数说明）。"""
    specs = list_skill_specs()
    if not specs:
        return "（暂无已注册 skill）"
    blocks: list[str] = ["# 可用 Skills", ""]
    for spec in specs:
        blocks.append(format_skill_for_ai(spec))
        blocks.append("")
        blocks.append(format_tools_for_ai(spec.tools))
        blocks.append("")
    return "\n".join(blocks).strip()


def skill_prompt_for_ai(skill_id: str, *, only: Sequence[str] | None = None) -> str:
    """单 skill 的 system 片段：规格 + 指定工具详情。"""
    spec = get_skill_spec(skill_id)
    names = tuple(only) if only is not None else spec.tools
    return f"{format_skill_for_ai(spec)}\n\n{format_tools_for_ai(names)}".strip()


def langchain_tools_for_skill(
    skill_id: str,
    *,
    only: Sequence[str] | None = None,
) -> list[BaseTool]:
    ensure_builtin_skills()
    return tools_for_skill(skill_id, only=only)


def make_skill_tools() -> list[BaseTool]:
    """把已注册 skill 变成 AI 可 ``bind_tools`` 的 StructuredTool。

    名称 = skill id；description / args_schema 来自 SkillSpec，供模型选型。
    调用结果为受理回执；真正长流程由 workflow / agent run 执行。
    """
    ensure_builtin_skills()
    out: list[BaseTool] = []
    for spec in list_skill_specs():

        def _runner(s: SkillSpec = spec, **kwargs: Any) -> str:
            return json.dumps(
                {"ok": True, "skill": s.id, "name": s.name, "args": kwargs},
                ensure_ascii=False,
            )

        out.append(
            StructuredTool.from_function(
                func=_runner,
                name=spec.id,
                description=spec.description.strip(),
                args_schema=spec.parameters,
            )
        )
    return out


def ensure_builtin_skills() -> None:
    """加载 builtin skill 规格模块（不 import workflow，避免环）。"""
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    _BUILTINS_LOADED = True
    # 仅加载 skill 规格；workflow 由调用方按需 import
    __import__("skills.market_research.skill")
