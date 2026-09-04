"""内置 MCP 服务目录 — 供桌面端展示（内部 Tool，非第三方 CLI）。

职责：
    返回与前端 ``McpListResponse`` 对齐的内置 MCP 配置。
    提示文案列出 registry 中的选品工具。
"""

from __future__ import annotations

from pathlib import Path

from src.tools.registry import list_tools

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SERVER_DIR = _REPO_ROOT / "server"


def list_builtin_mcp_servers() -> list[dict[str, object]]:
    """返回与前端 ``McpListResponse`` 对齐的内置 MCP 配置。"""
    server = str(_SERVER_DIR)
    tool_names = [spec.name for spec in list_tools()]
    return [
        {
            "id": "dingda",
            "name": "叮答爬虫工具",
            "transport": "stdio",
            "command": "uv",
            "args": ["run", "--directory", server, "dingda-mcp"],
            "enabled": True,
            "source": "builtin",
            "status": {
                "state": "ready",
                "label": "就绪",
                "hint": (
                    f"选品爬虫：{', '.join(tool_names)}。"
                    "闲鱼验证热度与价位；小红书收关键词；1688 未接入。"
                ),
                "badge_class": "bg-emerald-100 text-emerald-800",
            },
            "env": {"PYTHONUTF8": "1"},
            "tool_filter": {"include": tool_names},
        }
    ]
