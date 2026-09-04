"""DingDa MCP stdio 入口 — 对外只暴露爬虫 Tool。

职责：
    供桌面壳注入 Codex / OpenCode / Claude；工具面由 register allowlist 决定。
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from src.mcp.register import register_internal_tools


def create_mcp_server() -> FastMCP:
    """创建仅含 search / product 的 MCP server（Rust 拉起）。"""
    mcp = FastMCP("dingda")
    register_internal_tools(mcp)
    return mcp


def main() -> None:
    if sys.stdin.isatty():
        print(
            "dingda-mcp 是 MCP stdio server，不能交互式运行。\n"
            "请由桌面壳注入 MCP 配置后经 Codex / Claude 等外部 Agent 拉起。",
            file=sys.stderr,
        )
        raise SystemExit(2)

    create_mcp_server().run()


if __name__ == "__main__":
    main()
