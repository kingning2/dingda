"""内置 MCP 服务目录 — 供桌面端展示与 Codex 安装指引。"""

from __future__ import annotations

from pathlib import Path

from src.adapters.registry import is_vendor_installed
from src.mcp.exclusions import DEFAULT_EXCLUDED_TOOLS

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
_PLUGIN_DIR = _REPO_ROOT / "plugins" / "dingda-crawlers"


def _goofish_status() -> dict[str, str]:
    if not is_vendor_installed("goofish_cli"):
        return {
            "state": "missing_vendor",
            "label": "未同步",
            "hint": "请运行 backend/tooling/sync_vendor.py goofish_cli",
            "badge_class": "bg-amber-100 text-amber-800",
        }
    return {
        "state": "ready",
        "label": "就绪",
        "hint": "Codex 可通过 mcp__goofish__* 调用闲鱼爬虫工具",
        "badge_class": "bg-emerald-100 text-emerald-800",
    }


def list_builtin_mcp_servers() -> list[dict[str, object]]:
    """返回与前端 ``McpListResponse`` 对齐的内置 MCP 配置。"""
    backend = str(_BACKEND_DIR)
    return [
        {
            "id": "goofish",
            "name": "闲鱼爬虫 (goofish)",
            "transport": "stdio",
            "command": "uv",
            "args": ["run", "--directory", backend, "dingda-mcp"],
            "enabled": is_vendor_installed("goofish_cli"),
            "source": "builtin",
            "status": _goofish_status(),
            "env": {"PYTHONUTF8": "1"},
            "tool_filter": {
                "exclude": sorted(DEFAULT_EXCLUDED_TOOLS),
            },
        }
    ]


def codex_plugin_dir() -> Path:
    return _PLUGIN_DIR
