"""解析 Camoufox 可执行文件路径（壳已解压平台 zip）。

职责：
    给 Browser 适配器提供 ``executable_path``，避免官方 ``camoufox fetch`` 直连 GitHub。
    优先 ``DINGDA_CAMOUFOX_EXE``（由 Tauri 壳从安装包 zip 解压后注入）。

设计说明：
    - 安装包按平台打入 ``camoufox-{win.x86_64|mac.arm64|...}.zip``
    - 解压由 Rust ``zip`` crate 完成，落在 ``~/.dingda/v2/camoufox/current``
    - 本模块不再从 COS/网络下载
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("dingda.browser.camoufox_bin")

_CACHE_ROOT = Path.home() / ".dingda" / "v2" / "camoufox"


def _exe_name() -> str:
    return "camoufox.exe" if os.name == "nt" else "camoufox-bin"


def _find_exe(root: Path) -> Path | None:
    """在目录树里找 camoufox 启动器。"""
    names = ("camoufox.exe", "camoufox-bin", "camoufox")
    for name in names:
        direct = root / name
        if direct.is_file():
            return direct
    mac = root / "Camoufox.app" / "Contents" / "MacOS" / "camoufox"
    if mac.is_file():
        return mac
    for path in root.rglob("*"):
        if path.is_file() and path.name in names:
            return path
    return None


def resolve_camoufox_exe(*, download: bool = True) -> Path | None:
    """解析可用的 camoufox 可执行文件（download 参数保留兼容，忽略联网）。"""
    _ = download
    env_exe = (os.getenv("DINGDA_CAMOUFOX_EXE") or "").strip()
    if env_exe:
        path = Path(env_exe)
        if path.is_file():
            logger.info("camoufox exe from DINGDA_CAMOUFOX_EXE path=%s", path)
            return path
        logger.warning("DINGDA_CAMOUFOX_EXE 无效 path=%s", env_exe)

    bundled = (os.getenv("DINGDA_CAMOUFOX_DIR") or "").strip()
    if bundled:
        found = _find_exe(Path(bundled))
        if found:
            logger.info("camoufox exe from DINGDA_CAMOUFOX_DIR path=%s", found)
            return found

    cached = _find_exe(_CACHE_ROOT / "current")
    if cached:
        logger.info("camoufox exe from cache path=%s", cached)
        return cached

    # 开发态：不强制安装包 zip，交给 Camoufox 默认缓存（~/.cache / LocalAppData）
    logger.debug("camoufox exe unset; using library default path")
    return None


def require_camoufox_exe() -> Path:
    """必须拿到 exe；否则抛出可读错误。"""
    path = resolve_camoufox_exe()
    if path is None:
        raise RuntimeError(
            "未找到 Camoufox 浏览器。请确认安装包含当前平台的 camoufox-*.zip，"
            "并由桌面壳解压后设置 DINGDA_CAMOUFOX_EXE。"
        )
    return path
