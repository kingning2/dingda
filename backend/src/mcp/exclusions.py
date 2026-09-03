"""默认不向 Agent 暴露的 MCP 工具（对齐 goofish-cli bundle `.mcp.json` toolFilter）。"""

from __future__ import annotations

DEFAULT_EXCLUDED_TOOLS: frozenset[str] = frozenset(
    {
        "auth_login",
        "auth_reset_guard",
        "message_watch",
        "skills_install",
    }
)
