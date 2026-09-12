"""叮答工具的通用命令行入口（给「不走 MCP」的 agent 用）。

职责：
    按工具名建子命令，用该工具的 Pydantic 入参模型生成 ``--flag``；
    调 ``call_tool`` 跑一遍，把结果 JSON 打到 stdout。

设计说明：
    - 复用 registry：新增工具**自动**有 CLI，不用再写一个 ``*_cli.py``
    - 直播帧不用管：``call_tool`` 内部已按 ``DINGDA_AGENT_RUN_ID`` 推回 UI
    - stdout 只有 JSON（日志走 stderr），方便 agent 直接 ``json.loads``

使用示例：
    python -m src.tools.cli search --platform xianyu --query 键盘 --limit 20
    python -m src.tools.cli product --platform xianyu --item_id 733352707833
    python -m src.tools.cli compare --image "https://..."
    python -m src.tools.cli preview --url "https://www.goofish.com/item?id=1"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from pydantic import BaseModel

_JSON_TYPES = ("dict", "list")


def _force_utf8_stdout() -> None:
    """机器可读输出，固定 UTF-8（Windows 控制台是 GBK）。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _add_tool_parser(sub: Any, name: str, model: type[BaseModel], help_text: str) -> None:
    """按入参模型给子命令挂 ``--flag``。"""
    parser = sub.add_parser(name, help=help_text)
    for field_name, field in model.model_fields.items():
        flag = f"--{field_name.replace('_', '-')}"
        kind = str(field.annotation)
        parser.add_argument(
            flag,
            dest=field_name,
            required=field.is_required(),
            default=None,
            help=(field.description or "")[:120] + (
                "（JSON）" if any(t in kind for t in _JSON_TYPES) else ""
            ),
        )


def _build_input(model: type[BaseModel], ns: argparse.Namespace) -> BaseModel:
    """把命令行值收成入参模型；dict/list 字段按 JSON 解析。"""
    values: dict[str, Any] = {}
    for field_name, field in model.model_fields.items():
        raw = getattr(ns, field_name, None)
        if raw is None:
            continue
        if any(t in str(field.annotation) for t in _JSON_TYPES):
            values[field_name] = json.loads(raw)
        else:
            values[field_name] = raw
    return model.model_validate(values)


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    from src.tools.registry import call_tool, get_tool, list_tools

    parser = argparse.ArgumentParser(prog="python -m src.tools.cli", description="跑一个叮答工具")
    sub = parser.add_subparsers(dest="tool", required=True)
    for spec in list_tools():
        if spec.internal_only:
            continue  # 内部工具（修复子 agent 专用）不进这个面
        _add_tool_parser(sub, spec.name, spec.input_model, spec.description[:120])
    args = parser.parse_args(argv)

    try:
        spec = get_tool(args.tool)
        inp = _build_input(spec.input_model, args)
        out = asyncio.run(call_tool(args.tool, inp.model_dump()))
        payload = out.model_dump() if isinstance(out, BaseModel) else dict(out)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error_code": "cli.failed", "message": str(exc)[:300]},
                         ensure_ascii=False))
        return 1
    from src.agent.core.compress import compress_tool_payload

    payload = compress_tool_payload(payload, tool_name=args.tool)
    print(json.dumps(payload, ensure_ascii=False, default=str))
    return 0 if payload.get("ok") is not False else 1


if __name__ == "__main__":
    sys.exit(main())
