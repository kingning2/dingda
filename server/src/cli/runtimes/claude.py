"""Claude CLI 插头。

职责：
    实现 ``CliRuntime``：claude 的参数构建、MCP 注入模式与流格式。
"""

from __future__ import annotations

from typing import Any

from src.cli.base import CliRuntime


class ClaudeRuntime(CliRuntime):
    """Claude 插头：``claude -p --input-format stream-json``。"""

    id = "claude"
    name = "Claude"
    binary = "claude"
    path_env = "DINGDA_CLAUDE_PATH"
    mcp_mode = "claude-mcp-json"
    stream_format = "claude-stream-json"
    # ``-p --input-format stream-json`` 收的是 JSON 消息，不是纯文本
    stdin_format = "claude-stream-json"

    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """stream-json 进出 + 续聊 + 模型 + 额外可读目录。"""
        args = [
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        session = str(ctx.get("session_id") or "").strip()
        model = str(ctx.get("model_id") or "").strip()
        if session:
            args += ["--resume", session]
        if model and model != "default":
            args += ["--model", model]
        for d in ctx.get("extra_allowed_dirs") or []:
            path = str(d).strip()
            if path:
                args += ["--add-dir", path]
        args += ["--permission-mode", "bypassPermissions"]
        return args
