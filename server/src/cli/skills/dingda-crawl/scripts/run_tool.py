r"""DingDa crawl Skill 的工具入口。

职责：
    定位仓库 Server 目录，切换到该目录后复用 ``src.tools.cli``。
    让 Skill 只依赖一个可执行入口，不复制 CLI 参数和执行逻辑。

设计说明：
    - ``{{SERVER_DIR}}`` 由 Skill 安装器在落盘时替换
    - stdout 保持纯 JSON，日志继续走 stderr

使用示例：
    python run_tool.py search --platform xianyu --query "露营椅"
    python run_tool.py compare --help
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SERVER_DIR = Path(r"{{SERVER_DIR}}").resolve()


def _activate_server() -> None:
    """校验并切入 Server 目录，确保可导入 ``src.tools.cli``。"""
    cli_path = _SERVER_DIR / "src" / "tools" / "cli.py"
    if not cli_path.is_file():
        raise SystemExit(f"DingDa Server not found: {_SERVER_DIR}")
    os.chdir(_SERVER_DIR)
    sys.path.insert(0, str(_SERVER_DIR))


def main(argv: list[str] | None = None) -> int:
    """执行一次叮答 Tool CLI，并把退出码原样返回。"""
    _activate_server()
    from src.tools.cli import main as cli_main

    return cli_main(list(argv if argv is not None else sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
