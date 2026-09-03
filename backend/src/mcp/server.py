"""DingDa MCP stdio 入口 — `uv run dingda-mcp` / Codex plugin 调用。"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from src.mcp.goofish import register_goofish_tools


def create_mcp_server() -> FastMCP:
    mcp = FastMCP("goofish")
    register_goofish_tools(mcp)
    return mcp


def main() -> None:
    if sys.stdin.isatty():
        print(
            "dingda-mcp 是 MCP stdio server，不能交互式运行。\n"
            "请在 Codex / Claude Code / Cursor 中配置本命令，"
            "或执行 `codex plugin install` 安装 plugins/dingda-crawlers。",
            file=sys.stderr,
        )
        raise SystemExit(2)

    create_mcp_server().run()


if __name__ == "__main__":
    main()
