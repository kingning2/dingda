"""validate_selectors 的命令行形态。

职责：
    给「拿不到 MCP 工具」的子 agent 一条退路：读选择器 JSON，POST 到
    ``DINGDA_VALIDATE_URL``（修复现场的校验桥），把平台抽取脚本的输出打到 stdout。

设计说明：
    - 与 MCP 工具 ``validate_selectors`` 共用同一个 ``run_validate``
    - ``--selectors`` 收 JSON 字符串；``@路径`` 形式则从文件读，避免 shell 引号地狱

使用示例：
    python -m tools.validate_cli --selectors '{"price":"[class*=price]"}'
    python -m tools.validate_cli --selectors @selectors.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from tools.validate import ValidateInput, run_validate


def _load_selectors(raw: str) -> dict[str, str]:
    """解析 ``--selectors``：``@file`` 读文件，否则当 JSON 字符串。"""
    text = (raw or "").strip()
    if text.startswith("@"):
        text = Path(text[1:]).read_text(encoding="utf-8").strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("--selectors 要是 JSON 对象：{字段名: 选择器}")
    return {str(k): str(v) for k, v in data.items() if str(v).strip()}


def _force_utf8_stdout() -> None:
    """Windows 控制台默认 GBK，打不出 ``¥`` 之类会崩；这是机器可读输出，固定 UTF-8。"""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description="在修复现场的页面上试跑候选选择器")
    parser.add_argument(
        "--selectors",
        required=True,
        help='JSON 对象，或 @文件路径，如 \'{"price":"[class*=price]"}\'',
    )
    args = parser.parse_args(argv)
    try:
        selectors = _load_selectors(args.selectors)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": "bad-selectors", "message": str(exc)}, ensure_ascii=False))
        return 2
    out = asyncio.run(run_validate(ValidateInput(selectors=selectors)))
    payload = dict(out.payload)
    if out.error:
        payload["error"] = out.error
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not out.error else 1


if __name__ == "__main__":
    sys.exit(main())
