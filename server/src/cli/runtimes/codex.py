"""Codex CLI 插头。

职责：
    实现 ``CliRuntime``：codex 的参数构建、注入模式（skill）与流格式。

设计说明：
    - 工具面走 skill，不走 MCP（``mcp_mode = "codex-mcp"`` 保留为历史分支，
      当前角色侧返回 ``"none"``）。codex 没有原生 skill 概念，靠
      ``--add-dir <skill 目录>`` 把 ``~/.codex/skills`` 暴露给它读。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.cli.base import CliRuntime


def _skill_dirs() -> list[str]:
    """codex 该额外可读的 skill 目录（装 ``dingda-crawl`` 的地方）。"""
    raw = (os.getenv("DINGDA_SKILL_DIRS") or "").strip()
    if raw:
        return [p.strip() for p in raw.split(os.pathsep) if p.strip()]
    return [str(Path.home() / ".codex" / "skills")]


class CodexRuntime(CliRuntime):
    """Codex 插头：``codex exec``；Windows 上 codex 的 sandbox 收不紧，走 full-access。"""

    id = "codex"
    name = "Codex"
    binary = "codex"
    path_env = "DINGDA_CODEX_PATH"
    mcp_mode = "codex-mcp"
    stream_format = "codex-json"

    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """exec / resume + sandbox + 模型 + 额外可读目录（含 skill 目录）。"""
        session = str(ctx.get("session_id") or "").strip()
        model = str(ctx.get("model_id") or "").strip()
        cwd = str(ctx.get("cwd") or "").strip()
        # skill 目录必须可读，否则 agent 找不到 dingda-crawl 的命令
        allowed = list(ctx.get("extra_allowed_dirs") or []) + _skill_dirs()
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
            for d in allowed:
                path = str(d).strip()
                if path:
                    args += ["--add-dir", path]
        if model and model != "default":
            args += ["--model", model]
        return args
