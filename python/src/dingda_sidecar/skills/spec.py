"""Skill 规格 — 给 AI 看的名称、描述、参数与工具清单。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class SkillSpec:
    """一份 skill 的 AI 可见契约。

    - ``description``：何时调用、做什么（进 system / bind_tools）
    - ``parameters``：调用本 skill 时的入参 schema（Pydantic Field description）
    - ``tools``：本 skill 绑定的 ``tools.registry`` 工具名
    """

    id: str
    name: str
    description: str
    parameters: type[BaseModel]
    tools: tuple[str, ...]

    def parameters_schema(self) -> dict[str, Any]:
        return self.parameters.model_json_schema()

    def to_ai_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description.strip(),
            "parameters": self.parameters_schema(),
            "tools": list(self.tools),
        }


def _tool_one_liner(name: str) -> str:
    try:
        from dingda_sidecar.tools.registry import get_tool

        tool = get_tool(name)
        desc = str(getattr(tool, "description", "") or "").strip()
        if desc:
            first = desc.splitlines()[0].strip()
            return first[:160]
    except Exception:  # noqa: BLE001
        pass
    return "—"


def format_skill_for_ai(spec: SkillSpec) -> str:
    """把 skill 压成模型可读说明（做什么 + 参数 + 绑定工具摘要）。"""
    schema = spec.parameters_schema()
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    lines = [
        f"## Skill `{spec.id}` — {spec.name}",
        spec.description.strip(),
        "",
        "### 参数",
    ]
    if not props:
        lines.append("- （无）")
    else:
        for key, meta in props.items():
            if not isinstance(meta, dict):
                continue
            req = "必填" if key in required else "可选"
            typ = meta.get("type") or "any"
            desc = str(meta.get("description") or "").strip() or "—"
            extra = f"，默认 {meta['default']!r}" if "default" in meta else ""
            lines.append(f"- `{key}` ({typ}，{req}{extra})：{desc}")
    lines.append("")
    lines.append("### 绑定工具")
    if not spec.tools:
        lines.append("- （无）")
    else:
        for name in spec.tools:
            lines.append(f"- `{name}`：{_tool_one_liner(name)}")
    return "\n".join(lines)
