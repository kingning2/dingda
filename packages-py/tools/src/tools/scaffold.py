"""Tool 脚手架：生成一个可注册的新工具目录。

职责：
    ``python -m tools.scaffold <name>`` 在 ``tools/`` 下创建 ``<name>/__init__.py``
    骨架（文件头三段式 + Input/Output + run_* + spec），registry 下次导入即自动发现。

设计说明：
    - 只生成骨架，不猜测平台细节；跑通后再把 run_* 里换成真实抓取逻辑
    - name 必须是小写下划线标识符，且不与现有目录 / 平铺模块冲突

使用示例：
    uv run python -m tools.scaffold coupon
    uv run python -m tools.cli list   # 验证新工具已被 registry 发现
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NoReturn

_TEMPLATE = '''"""<NAME> Tool：<一句话说清这个工具做什么>。

职责：
    契约（Input/Output）与执行放同一文件；registry 自动发现本目录的 ``spec``。

设计说明：
    - <输入的关键约束，如 platform 取值、是否需要登录 cookie>
    - 不 import Playwright / Camoufox；浏览器能力一律走 Crawler → BrowserPort

使用示例：
    out = await run_<NAME>(<INP>(<示例参数>))
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from tools.spec import ToolSpec

logger = logging.getLogger("dingda.tools.<NAME>")

TOOL_NAME = "<NAME>"
TOOL_DESCRIPTION = "<NAME>：<一句话能力描述，给 LLM 看的提示词>"

DEFAULT_TIMEOUT_S = 60.0


class <INP>(BaseModel):
    """<NAME> 入参。"""

    query: str = Field(description="示例入参，按需替换")


class <OUT>(BaseModel):
    """<NAME> 出参。"""

    ok: bool = True
    message: str | None = None


async def run_<NAME>(inp: <INP>) -> <OUT>:
    """执行 <NAME>；失败用 ok=False + error_code 表达，不抛异常。"""
    logger.info("<NAME> start query=%s", inp.query)
    # TODO: 在这里实现真实逻辑；需要登录 cookie 时用
    # tools.account_cookie.resolve_crawl_cookie(platform, None)
    logger.info("<NAME> done")
    return <OUT>(ok=True, message=f"收到 {inp.query!r}（脚手架占位实现）")


spec = ToolSpec(
    name=TOOL_NAME,
    description=TOOL_DESCRIPTION,
    input_model=<INP>,
    output_model=<OUT>,
    handler=run_<NAME>,  # type: ignore[arg-type]
    timeout_s=DEFAULT_TIMEOUT_S,
)
'''


def _fail(message: str) -> NoReturn:
    """打印错误并退出。"""
    print(f"scaffold 失败：{message}", file=sys.stderr)
    raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    """按模板生成 tools/<name>/__init__.py。"""
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        _fail("用法：python -m tools.scaffold <tool_name>")
    name = argv[0]
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        _fail(f"工具名 {name!r} 必须是小写下划线标识符（字母开头）")

    pkg_dir = Path(__file__).resolve().parent
    target = pkg_dir / name
    if target.exists():
        _fail(f"目录已存在：{target}")
    flat = pkg_dir / f"{name}.py"
    if flat.exists():
        _fail(f"与平铺模块冲突：{flat}")

    pascal = "".join(part.capitalize() for part in name.split("_"))
    body = (
        _TEMPLATE.replace("<NAME>", name)
        .replace("<INP>", f"{pascal}Input")
        .replace("<OUT>", f"{pascal}Output")
    )
    target.mkdir()
    (target / "__init__.py").write_text(body, encoding="utf-8", newline="\n")
    print(f"已创建 {target / '__init__.py'}")
    print("下一步：")
    print(f"  1. 把 run_{name} 换成真实逻辑（契约、错误模型、超时都在同文件里）")
    print("  2. uv run python -m tools.cli list   # 验证 registry 已发现")


if __name__ == "__main__":
    main()
