"""外部 CLI Runtime 插头注册表。

职责：
    按 runtime id 取出插头（[base.py](base.py) 的 ``CliRuntime``），并解析各 CLI 的
    可执行文件路径。
    已实现：codex / claude / opencode / workbuddy。

设计说明：
    - 插头放 ``runtimes/<id>.py``；参数 / MCP 模式 / 流格式的差异只在插头里
    - 探测顺序：preferred → ``DINGDA_*_PATH`` → 托管目录 → PATH → 已知安装目录
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from src.cli.base import CliRuntime
from src.cli.runtimes.claude import ClaudeRuntime
from src.cli.runtimes.codex import CodexRuntime
from src.cli.runtimes.opencode import OpenCodeRuntime
from src.cli.runtimes.workbuddy import WorkBuddyRuntime

logger = logging.getLogger("dingda.cli")


_RUNTIMES: dict[str, CliRuntime] = {
    runtime.id: runtime
    for runtime in (
        CodexRuntime(),
        ClaudeRuntime(),
        OpenCodeRuntime(),
        WorkBuddyRuntime(),
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
