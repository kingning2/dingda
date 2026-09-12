r"""DingDa crawl Skill 的工具入口。

职责：
    复用 ``tools.cli``，让 Skill 只依赖一个可执行入口，不复制 CLI 参数和执行逻辑。

设计说明：
    - 叮答工具包已装进 venv：用渲染时的绝对解释器即可在任意目录导入
    - stdout 保持纯 JSON，日志继续走 stderr

使用示例：
    python run_tool.py search --platform xianyu --query "露营椅"
    python run_tool.py compare --help
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """执行一次叮答 Tool CLI，并把退出码原样返回。"""
    from tools.cli import main as cli_main

    return cli_main(list(argv if argv is not None else sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
