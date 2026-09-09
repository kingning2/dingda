"""外部 CLI Runtime 注册表。

职责：
    按 runtime id 描述二进制名、参数构建与 MCP 注入模式。
    已实现：codex / claude / opencode。

设计说明：
    - 对齐原 Tauri ``runtime/defs`` 的最小子集
    - 探测 PATH / ``DINGDA_*_PATH`` 环境变量
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("dingda.agent.runtimes")


@dataclass(frozen=True)
class RuntimeSpec:
    """单个外部 CLI 的插座描述。"""

    id: str
    name: str
    binary: str
    path_env: str
    mcp_mode: str  # "codex-mcp" | "claude-mcp-json" | "opencode-env-content" | "none"
    build_args: Callable[[dict[str, Any]], list[str]]
    prompt_via_stdin: bool = True
    stream_format: str = "codex-json"  # codex-json | claude-stream-json | opencode-json | plain
    fallback_binaries: tuple[str, ...] = ()


def _codex_args(ctx: dict[str, Any]) -> list[str]:
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


def _claude_args(ctx: dict[str, Any]) -> list[str]:
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


def _opencode_args(ctx: dict[str, Any]) -> list[str]:
    """对齐 Tauri ``opencode_build_args``：``run --format json --auto --thinking``。"""
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


_SPECS: dict[str, RuntimeSpec] = {
    "codex": RuntimeSpec(
        id="codex",
        name="Codex",
        binary="codex",
        path_env="DINGDA_CODEX_PATH",
        mcp_mode="codex-mcp",
        build_args=_codex_args,
        stream_format="codex-json",
    ),
    "claude": RuntimeSpec(
        id="claude",
        name="Claude",
        binary="claude",
        path_env="DINGDA_CLAUDE_PATH",
        mcp_mode="claude-mcp-json",
        build_args=_claude_args,
        stream_format="claude-stream-json",
    ),
    "opencode": RuntimeSpec(
        id="opencode",
        name="OpenCode",
        binary="opencode",
        path_env="DINGDA_OPENCODE_PATH",
        mcp_mode="opencode-env-content",
        build_args=_opencode_args,
        stream_format="opencode-json",
        fallback_binaries=("opencode-cli",),
    ),
}


def list_runtime_ids() -> list[str]:
    """已实现插头的 runtime id。"""
    return sorted(_SPECS)


def get_runtime(runtime_id: str) -> RuntimeSpec:
    """按 id 取规格；未知则 KeyError。"""
    key = runtime_id.strip().lower()
    if key not in _SPECS:
        raise KeyError(runtime_id)
    return _SPECS[key]


def resolve_binary(spec: RuntimeSpec, *, preferred: str | None = None) -> Path | None:
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

    override = os.getenv(spec.path_env, "").strip()
    if override:
        path = _as_exe_path(override)
        if path is not None:
            return path

    managed = _managed_binary(spec)
    if managed is not None:
        return managed

    search_path = _search_path_env()
    for name in (spec.binary, *spec.fallback_binaries):
        found = shutil.which(name, path=search_path)
        if found:
            return Path(found)
        found_cmd = shutil.which(f"{name}.cmd", path=search_path)
        if found_cmd:
            return Path(found_cmd)

    known = _known_location_binary(spec)
    if known is not None:
        return known

    logger.warning("runtime binary missing id=%s env=%s", spec.id, spec.path_env)
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


def _managed_binary(spec: RuntimeSpec) -> Path | None:
    """探测叮答一键下载落盘的二进制。"""
    home = Path.home()
    root = home / ".dingda" / "v2" / "runtimes" / spec.id
    return _first_existing_binary(root, spec)


def _known_location_binary(spec: RuntimeSpec) -> Path | None:
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
        found = _first_existing_binary(directory, spec)
        if found is not None:
            return found
    return None


def _first_existing_binary(directory: Path, spec: RuntimeSpec) -> Path | None:
    if not directory.is_dir():
        return None
    names = [spec.binary, *spec.fallback_binaries]
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
