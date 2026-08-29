"""工具注册表 — 全局 StructuredTool 工厂 + skill 绑定 + AI schema。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.tools import BaseTool

ToolFactory = Callable[[], BaseTool]

_TOOLS: dict[str, ToolFactory] = {}
_SKILL_TOOLS: dict[str, tuple[str, ...]] = {}


def register_tool(name: str, factory: ToolFactory) -> None:
    key = name.strip()
    if not key:
        raise ValueError("tool name 为空")
    _TOOLS[key] = factory


def bind_skill_tools(skill_id: str, tool_names: Sequence[str]) -> None:
    sid = skill_id.strip()
    if not sid:
        raise ValueError("skill_id 为空")
    names = tuple(n.strip() for n in tool_names if str(n).strip())
    unknown = [n for n in names if n not in _TOOLS]
    if unknown:
        raise KeyError(f"skill={sid} 引用未注册工具: {unknown}")
    _SKILL_TOOLS[sid] = names


def list_tools() -> list[str]:
    return sorted(_TOOLS)


def list_skill_tools(skill_id: str) -> tuple[str, ...]:
    return _SKILL_TOOLS.get(skill_id.strip(), ())


def get_tool(name: str) -> BaseTool:
    factory = _TOOLS.get(name)
    if factory is None:
        raise KeyError(f"unknown tool: {name}")
    tool = factory()
    if not getattr(tool, "description", None):
        raise ValueError(f"tool={name} 缺少 AI description")
    return tool


def make_tools(names: Sequence[str]) -> list[BaseTool]:
    return [get_tool(n) for n in names]


def tools_for_skill(skill_id: str, *, only: Sequence[str] | None = None) -> list[BaseTool]:
    names = list_skill_tools(skill_id)
    if only is not None:
        allow = set(only)
        names = tuple(n for n in names if n in allow)
    return make_tools(names)


def tool_ai_schema(name: str) -> dict[str, Any]:
    """单个工具的 AI 可见 schema（name / description / parameters）。"""
    tool = get_tool(name)
    schema: dict[str, Any] = {
        "name": tool.name,
        "description": str(tool.description or "").strip(),
    }
    args = getattr(tool, "args_schema", None)
    if args is not None and hasattr(args, "model_json_schema"):
        schema["parameters"] = args.model_json_schema()
    elif args is not None and hasattr(args, "schema"):
        schema["parameters"] = args.schema()
    else:
        schema["parameters"] = {"type": "object", "properties": {}}
    return schema


def format_tools_for_ai(names: Sequence[str]) -> str:
    """把工具列表格式化成模型可读说明。"""
    lines = ["### 工具详情（供调用）"]
    for name in names:
        spec = tool_ai_schema(name)
        lines.append(f"#### `{spec['name']}`")
        lines.append(str(spec.get("description") or "—"))
        props = (spec.get("parameters") or {}).get("properties") or {}
        required = set((spec.get("parameters") or {}).get("required") or [])
        if not props:
            lines.append("参数：无")
        else:
            lines.append("参数：")
            for key, meta in props.items():
                if not isinstance(meta, dict):
                    continue
                req = "必填" if key in required else "可选"
                typ = meta.get("type") or "any"
                desc = str(meta.get("description") or "").strip() or "—"
                default = f"，默认 {meta['default']!r}" if "default" in meta else ""
                lines.append(f"- `{key}` ({typ}，{req}{default})：{desc}")
        lines.append("")
    return "\n".join(lines).strip()


def _register_builtins() -> None:
    if _TOOLS:
        return

    from dingda_sidecar.tools.alibaba.bindings import make_alibaba_search_tool
    from dingda_sidecar.tools.knowledge.bindings import make_knowledge_retrieve_tool
    from dingda_sidecar.tools.web.bindings import make_web_fetch_tool, make_web_scrape_tool
    from dingda_sidecar.tools.xianyu.bindings import make_xianyu_search_tool

    register_tool("web_fetch", make_web_fetch_tool)
    register_tool("web_scrape", make_web_scrape_tool)
    register_tool("alibaba_search", make_alibaba_search_tool)
    register_tool("xianyu_search", make_xianyu_search_tool)
    register_tool("knowledge_retrieve", make_knowledge_retrieve_tool)


_register_builtins()
