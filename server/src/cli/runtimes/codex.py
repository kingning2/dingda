"""Codex CLI 插头。

职责：
    实现 ``CliRuntime``：codex 的参数构建、MCP 注入模式与流格式。
"""

from __future__ import annotations

import os
from typing import Any

from src.cli.base import CliRuntime


class CodexRuntime(CliRuntime):
    """Codex 插头：``codex exec``；Windows 上 codex 的 sandbox 收不紧，走 full-access。"""

    id = "codex"
    name = "Codex"
    binary = "codex"
    path_env = "DINGDA_CODEX_PATH"
    mcp_mode = "codex-mcp"
    stream_format = "codex-json"

    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """exec / resume + sandbox + 模型 + 额外可读目录。"""
        session = str(ctx.get("session_id") or "").strip()
        model = str(ctx.get("model_id") or "").strip()
        cwd = str(ctx.get("cwd") or "").strip()
        danger = os.name == "nt"
        args = ["exec", "--json", "--skip-git-repo-check"]
        if session:
            args = ["exec", "resume", "--json", "--skip-git-repo-check"]
            args += (
                ["-c", 'sandbox_mode="danger-full-access"']
                if danger
                else [
                    "-c",
                    'sandbox_mode="workspace-write"',
                    "-c",
                    "sandbox_workspace_write.network_access=true",
                ]
            )
            args.append(session)
        else:
            args += (
                ["--sandbox", "danger-full-access"]
                if danger
                else [
                    "--sandbox",
                    "workspace-write",
                    "-c",
                    "sandbox_workspace_write.network_access=true",
                ]
            )
            if cwd:
                args += ["-C", cwd]
            for d in ctx.get("extra_allowed_dirs") or []:
                path = str(d).strip()
                if path:
                    args += ["--add-dir", path]
        if model and model != "default":
            args += ["--model", model]
        return args
