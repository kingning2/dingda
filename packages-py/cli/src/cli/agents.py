"""外部 CLI 插头：codex / claude / opencode 的差异与注册表。

职责：
    一个文件收完三个 CLI 插头（各自的参数构建与流格式），并提供插头注册表
    与可执行文件探测。生命周期（spawn / 流解析 / 日志）在 ``base.CliRuntime``。

设计说明：
    - 插头只写「本 CLI 长什么样」：``id`` / ``name`` / ``binary`` / ``path_env`` /
      ``stream_format`` 与 ``build_args``；差异之外的能力全在基类
    - 工具面统一走 skill（``cli/skill.py``），插头只负责把 skill 目录暴露给 CLI 读
    - ``ctx`` 里三个 CLI 都要的字段（session / model / cwd）走 ``_ctx_value``，
      不各写一遍 ``str(ctx.get(...) or "").strip()``
    - 探测顺序：preferred → ``DINGDA_*_PATH`` → 托管目录 → PATH
      （Windows 会并上注册表 PATH）→ 已知安装目录

使用示例：
    runtime = get_runtime("codex")
    async for event in runtime.run("搜闲鱼露营椅", role="parent"):
        ...
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, ClassVar

from cli.base import CliRuntime
from core.errors import AppError

logger = logging.getLogger("dingda.cli.agents")


def _ctx_value(ctx: dict[str, Any], key: str) -> str:
    """取 ctx 里的字符串参数（session_id / model_id / cwd …），缺省空串。"""
    return str(ctx.get(key) or "").strip()


def _model_args(flag: str, ctx: dict[str, Any]) -> list[str]:
    """模型参数；``default`` 等于没指定，不写进命令行。"""
    model = _ctx_value(ctx, "model_id")
    return [flag, model] if model and model != "default" else []


def _dir_args(flag: str, ctx: dict[str, Any], extra: list[str] | None = None) -> list[str]:
    """额外可读目录参数（含 skill 目录）。"""
    args: list[str] = []
    for raw in [*(ctx.get("extra_allowed_dirs") or []), *(extra or [])]:
        path = str(raw).strip()
        if path:
            args += [flag, path]
    return args


def _codex_skill_dirs() -> list[str]:
    """codex 该额外可读的 skill 目录（``dingda-crawl`` 的安装位）。

    与 ``skill.install`` 写出的 ``~/.codex/skills`` 对齐；``DINGDA_SKILL_DIRS``
    供开发态改到仓库里的模板目录。
    """
    raw = (os.getenv("DINGDA_SKILL_DIRS") or "").strip()
    if raw:
        return [p.strip() for p in raw.split(os.pathsep) if p.strip()]
    return [str(Path.home() / ".codex" / "skills")]


class CodexRuntime(CliRuntime):
    """Codex 插头：``codex exec``；Windows 上 codex 的 sandbox 收不紧，走 full-access。"""

    id: ClassVar[str] = "codex"
    name: ClassVar[str] = "Codex"
    binary: ClassVar[str] = "codex"
    path_env: ClassVar[str] = "DINGDA_CODEX_PATH"
    stream_format: ClassVar[str] = "codex-json"

    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """exec / resume + sandbox + 模型 + 额外可读目录（含 skill 目录）。"""
        session = _ctx_value(ctx, "session_id")
        cwd = _ctx_value(ctx, "cwd")
        danger = os.name == "nt"
        # skill 目录必须可读，否则 agent 找不到 dingda-crawl 的命令
        extra_dirs = _codex_skill_dirs()
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
            args += _dir_args("--add-dir", ctx, extra_dirs)
        return args + _model_args("--model", ctx)


class ClaudeRuntime(CliRuntime):
    """Claude 插头：``claude -p --input-format stream-json``。"""

    id: ClassVar[str] = "claude"
    name: ClassVar[str] = "Claude"
    binary: ClassVar[str] = "claude"
    path_env: ClassVar[str] = "DINGDA_CLAUDE_PATH"
    stream_format: ClassVar[str] = "claude-stream-json"
    # ``-p --input-format stream-json`` 收的是 JSON 消息，不是纯文本
    stdin_format: ClassVar[str] = "claude-stream-json"

    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """stream-json 进出 + 续聊 + 模型 + 额外可读目录。"""
        session = _ctx_value(ctx, "session_id")
        args = [
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if session:
            args += ["--resume", session]
        args += _model_args("--model", ctx)
        args += _dir_args("--add-dir", ctx)
        return args + ["--permission-mode", "bypassPermissions"]


class OpenCodeRuntime(CliRuntime):
    """OpenCode 插头：``opencode run --format json --auto --thinking``。"""

    id: ClassVar[str] = "opencode"
    name: ClassVar[str] = "OpenCode"
    binary: ClassVar[str] = "opencode"
    path_env: ClassVar[str] = "DINGDA_OPENCODE_PATH"
    stream_format: ClassVar[str] = "opencode-json"
    fallback_binaries: ClassVar[tuple[str, ...]] = ("opencode-cli",)

    def build_args(self, ctx: dict[str, Any]) -> list[str]:
        """对齐 Tauri ``opencode_build_args``。"""
        args = ["run", "--format", "json", "--auto", "--thinking"]
        cwd = _ctx_value(ctx, "cwd")
        if cwd:
            args += ["--dir", cwd]
        session = _ctx_value(ctx, "session_id")
        if session:
            args += ["-s", session]
        args += _model_args("-m", ctx)
        variant = _ctx_value(ctx, "reasoning") or _ctx_value(ctx, "variant")
        if variant and variant != "default":
            args += ["--variant", variant]
        return args


_RUNTIMES: dict[str, CliRuntime] = {
    runtime.id: runtime
    for runtime in (
        CodexRuntime(),
        ClaudeRuntime(),
        OpenCodeRuntime(),
    )
}


def list_runtime_ids() -> list[str]:
    """已实现插头的 runtime id。"""
    return sorted(_RUNTIMES)


def get_runtime(runtime_id: str) -> CliRuntime:
    """按 id 取插头；未知则 KeyError。"""
    key = runtime_id.strip().lower()
    if key not in _RUNTIMES:
        raise KeyError(runtime_id)
    return _RUNTIMES[key]


def resolve_binary(runtime: CliRuntime, *, preferred: str | None = None) -> Path | None:
    """解析可执行文件路径。

    顺序：前端/扫描传入的 ``preferred`` → ``DINGDA_*_PATH`` → 托管目录
    →（Windows 刷新后的）PATH → 已知安装目录。

    说明：
        Tauri 会读注册表 User/Machine PATH（含 ``~/.opencode/bin``），
        Python 进程 PATH 可能是启动时的旧值；故此处补注册表 PATH 与已知目录。
    """
    if preferred and preferred.strip():
        path = _as_exe_path(preferred)
        if path is not None:
            return path

    override = os.getenv(runtime.path_env, "").strip()
    if override:
        path = _as_exe_path(override)
        if path is not None:
            return path

    managed = _managed_binary(runtime)
    if managed is not None:
        return managed

    search_path = _search_path_env()
    for name in (runtime.binary, *runtime.fallback_binaries):
        found = shutil.which(name, path=search_path)
        if found:
            return Path(found)
        found_cmd = shutil.which(f"{name}.cmd", path=search_path)
        if found_cmd:
            return Path(found_cmd)

    known = _known_location_binary(runtime)
    if known is not None:
        return known

    logger.warning("runtime binary missing id=%s env=%s", runtime.id, runtime.path_env)
    return None


def _as_exe_path(raw: str) -> Path | None:
    """规范化路径（去掉 Windows ``\\\\?\\`` 前缀）；文件存在才返回。"""
    text = raw.strip().strip('"')
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[8:]
    elif text.startswith("\\\\?\\"):
        text = text[4:]
    elif text.startswith("//?/"):
        text = text[4:]
    path = Path(text)
    return path if path.is_file() else None


def _search_path_env() -> str:
    """进程 PATH；Windows 再并上注册表 User/Machine PATH（对齐 Tauri）。"""
    current = os.environ.get("PATH", "")
    if os.name != "nt":
        return current
    fresh = _windows_registry_path()
    if not fresh:
        return current
    # 注册表在前：叮答启动后新装的 CLI 也能被 which 到
    return f"{fresh};{current}" if current else fresh


def _windows_registry_path() -> str:
    """读 HKLM + HKCU 的 Path，不依赖当前进程环境。"""
    import winreg

    parts: list[str] = []
    for root, subkey in (
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ):
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        text = str(value or "").strip()
        if text:
            parts.append(text)
    return ";".join(parts)


def _managed_binary(runtime: CliRuntime) -> Path | None:
    """探测叮答一键下载落盘的二进制。"""
    home = Path.home()
    root = home / ".dingda" / "v2" / "runtimes" / runtime.id
    return _first_existing_binary(root, runtime)


def _known_location_binary(runtime: CliRuntime) -> Path | None:
    """对齐 Tauri ``known_locations``，并补官方安装器目录。"""
    home = Path.home()
    dirs = [
        home / ".opencode" / "bin",  # OpenCode 官方安装器（常不在进程 PATH）
        home / ".local" / "bin",
        home / ".cargo" / "bin",
        home / ".npm-global" / "bin",
        home / "node_modules" / ".bin",
        home / "AppData" / "Roaming" / "npm",
        home / "AppData" / "Local" / "Programs",
    ]
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        dirs.append(Path(appdata) / "npm")
    local = os.getenv("LOCALAPPDATA", "").strip()
    if local:
        dirs.append(Path(local) / "Programs")
    pf = os.getenv("ProgramFiles", "").strip()
    if pf:
        dirs.append(Path(pf) / "nodejs")
    for directory in dirs:
        found = _first_existing_binary(directory, runtime)
        if found is not None:
            return found
    return None


def _first_existing_binary(directory: Path, runtime: CliRuntime) -> Path | None:
    if not directory.is_dir():
        return None
    names = [runtime.binary, *runtime.fallback_binaries]
    candidates: list[str] = []
    if os.name == "nt":
        for name in names:
            candidates.extend([f"{name}.exe", f"{name}.cmd", name])
    else:
        candidates.extend(names)
    for name in candidates:
        path = directory / name
        if path.is_file():
            return path
    return None
