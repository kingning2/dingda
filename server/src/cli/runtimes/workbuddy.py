"""WorkBuddy CLI 插头。

职责：
    实现 ``CliRuntime``：WorkBuddy（CodeBuddy Code）的可执行入口探测、参数构建、
    注入模式（skill）与流格式。

设计说明：
    - 接口与 claude 同形：``-p --output-format stream-json --input-format stream-json``，
      所以 stream_format / stdin_format 复用 claude 那套解析
    - 可执行入口是 node 脚本（``cli/dist/codebuddy.js``），不是单文件 exe：
      ``build_args`` 需要把「脚本路径」放在最前，见 ``_eval_script()``
    - **工具面走 skill，不走 MCP**：``mcp_mode = "none"``，工具由
      ``src/tools/skill.py`` 渲染的 ``dingda-crawl`` SKILL.md 装到
      ``~/.codebuddy/skills/`` 提供 —— 与 codex / claude / opencode 同一条路径
    - 无头运行要 ``--permission-mode bypassPermissions``，否则子 agent 起不来
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from src.cli.base import CliRuntime

logger = logging.getLogger("dingda.cli.runtimes.workbuddy")

# WorkBuddy 桌面壳内的 CLI 脚本（相对安装目录）
# 打包态落在 ``resources/app.asar.unpacked/cli/dist/codebuddy.js``
_BUNDLED_SCRIPT = Path("resources") / "app.asar.unpacked" / "cli" / "dist" / "codebuddy.js"
# 少数布局把 cli 直接放在安装根下
_BUNDLED_SCRIPT_ALT = Path("cli") / "dist" / "codebuddy.js"

# WorkBuddy / CodeBuddy Code 读 skill 的目录（相对用户主目录）
# 与 src/tools/skill.py 的 _RUNTIME_SKILL_DIRS 保持一致
SKILL_DIR = Path(".codebuddy") / "skills"
SKILL_NAME = "dingda-crawl"


def _eval_script() -> Path | None:
    """WorkBuddy 安装目录里的 CLI 脚本（``<root>/cli/dist/codebuddy.js``）。

    探测顺序：
        1. ``DINGDA_WORKBUDDY_CLI`` 直接指向脚本本身
        2. ``DINGDA_WORKBUDDY_ROOT`` 下的 ``cli/dist/codebuddy.js``
        3. 常见安装位置（WorkBuddyAI / WorkBuddy）
    """
    direct = (os.getenv("DINGDA_WORKBUDDY_CLI") or "").strip()
    if direct:
        path = Path(direct.strip('"'))
        if path.is_file():
            return path

    roots: list[Path] = []
    env_root = (os.getenv("DINGDA_WORKBUDDY_ROOT") or "").strip()
    if env_root:
        roots.append(Path(env_root.strip('"')))
    local = (os.getenv("LOCALAPPDATA") or "").strip()
    prow = os.getenv("ProgramFiles", "").strip()
    if local:
        roots.append(Path(local) / "Programs")
    if prow:
        roots.append(Path(prow))
    roots += [Path("D:/workbuddy"), Path("C:/workbuddy")]

    for root in roots:
        # 根目录本身可能就是安装目录（如 D:/workbuddy/WorkBuddyAI）
        candidates = [
            root / _BUNDLED_SCRIPT,
            root / _BUNDLED_SCRIPT_ALT,
        ]
        for name in ("WorkBuddyAI", "WorkBuddy"):
            candidates += [
                root / name / _BUNDLED_SCRIPT,
                root / name / _BUNDLED_SCRIPT_ALT,
            ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    return None


def skill_path(home: Path | None = None) -> Path:
    """本 runtime 读 ``dingda-crawl`` skill 的 SKILL.md 路径。"""
    return (home or Path.home()) / SKILL_DIR / SKILL_NAME / "SKILL.md"


def skill_installed(home: Path | None = None) -> bool:
    """skill 是否已装到 WorkBuddy 的 skills 目录。"""
    return skill_path(home).is_file()


class WorkBuddyRuntime(CliRuntime):
    """WorkBuddy 插头：``codebuddy -p --output-format stream-json``。

    入口是 node 脚本，故 ``binary`` 交给 ``node``，脚本路径由 ``build_args`` 补在最前；
    找不到 node 时退回脚本自身（安装包里的 ``codebuddy`` 是带 shebang 的可执行包装）。

    工具面由 ``~/.codebuddy/skills/dingda-crawl/SKILL.md`` 提供（``mcp_mode="none"``），
    装法见 ``src/tools/skill.py``：``python -m src.tools.skill --install``。
    """

    id = "workbuddy"
    name = "WorkBuddy"
    binary = "node"
    path_env = "DINGDA_WORKBUDDY_PATH"
    # 注入方式：skill（SKILL.md），不注入 MCP
    mcp_mode = "none"
    stream_format = "claude-stream-json"
    # 与 claude 一致：``--input-format stream-json`` 收的是一条 JSON 消息
    stdin_format = "claude-stream-json"

    def resolve_binary(self, *, preferred: str | None = None) -> Path | None:
        """优先用 WorkBuddy 自带的 node，其次系统 node。"""
        script = _eval_script()
        if script is not None:
            # 打包态：<install>/resources/app.asar.unpacked/cli/dist/codebuddy.js
            # 壳内 node 在 <install>/resources/app.asar.unpacked/node/node.exe
            for up in (4, 3, 2):
                if len(script.parents) > up:
                    bundled = script.parents[up] / "node" / "node.exe"
                    if bundled.is_file():
                        return bundled
        return super().resolve_binary(preferred=preferred)

    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """stream-json 进出 + 无头权限 + 续聊 + 模型 + 额外可读目录。"""
        args: list[str] = []
        script = _eval_script()
        if script is not None:
            # node <script> -p --output-format ...
            args.append(str(script))

        args += [
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
        # 无头子 agent 必须跳过权限校验，否则工具调用会被拦下
        args += ["--permission-mode", "bypassPermissions"]
        return args
