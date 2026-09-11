"""OpenCode CLI 插头。

职责：
    实现 ``CliRuntime``：opencode 的参数构建、MCP 注入模式与流格式。
"""

from __future__ import annotations

from typing import Any

from src.cli.base import CliRuntime


class OpenCodeRuntime(CliRuntime):
    """OpenCode 插头：``opencode run --format json --auto --thinking``。"""

    id = "opencode"
    name = "OpenCode"
    binary = "opencode"
    path_env = "DINGDA_OPENCODE_PATH"
    mcp_mode = "opencode-env-content"
    stream_format = "opencode-json"
    fallback_binaries = ("opencode-cli",)

    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """对齐 Tauri ``opencode_build_args``。"""
        args = ["run", "--format", "json", "--auto", "--thinking"]
        cwd = str(ctx.get("cwd") or "").strip()
        if cwd:
            args += ["--dir", cwd]
        session = str(ctx.get("session_id") or "").strip()
        if session:
            args += ["-s", session]
        model = str(ctx.get("model_id") or "").strip()
        if model and model != "default":
            args += ["-m", model]
        variant = str(ctx.get("reasoning") or ctx.get("variant") or "").strip()
        if variant and variant != "default":
            args += ["--variant", variant]
        return args
