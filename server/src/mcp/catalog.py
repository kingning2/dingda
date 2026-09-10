"""内置 MCP 服务目录 — 供桌面端展示（内部 Tool，非第三方 CLI）。

职责：
    返回与前端 ``McpListResponse`` 对齐的内置 MCP 配置。
    提示文案列出 registry 中的选品工具。
"""

from __future__ import annotations

import os
from pathlib import Path

from src.tools.registry import list_tools


def _server_dir() -> Path:
    env = (os.getenv("DINGDA_SERVER_DIR") or "").strip()
    if env:
        return Path(env)
    # catalog 在 server/src/mcp/ → parents[2] == server/
    return Path(__file__).resolve().parents[2]


def list_builtin_mcp_servers() -> list[dict[str, object]]:
    """返回与前端 ``McpListResponse`` 对齐的内置 MCP 配置。"""
    server = str(_server_dir())
    tool_names = [spec.name for spec in list_tools() if not spec.internal_only]
    python = (os.getenv("DINGDA_PYTHON") or "").strip()
    if python:
        command = python
        args: list[str] = ["-m", "src.mcp.server"]
    else:
        uv = (os.getenv("DINGDA_UV") or "").strip() or "uv"
        command = uv
        args = ["run", "--directory", server, "dingda-mcp"]
    return [
        {
            "id": "dingda",
            "name": "叮答爬虫工具",
            "transport": "stdio",
            "command": command,
            "args": args,
            "enabled": True,
            "source": "builtin",
            "status": {
                "state": "ready",
                "label": "就绪",
                "hint": (
                    f"选品工具：{', '.join(tool_names)}。"
                    "闲鱼/小红书走浏览器爬虫；ali1688 走官方找货 API（需 ALI_1688_AK）。"
                ),
                "badge_class": "bg-emerald-100 text-emerald-800",
            },
            "env": {"PYTHONUTF8": "1", "DINGDA_SERVER_DIR": server},
            "tool_filter": {"include": tool_names},
        }
    ]
