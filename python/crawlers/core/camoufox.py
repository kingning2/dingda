"""Camoufox / Chromium 统一启动入口（Cookie 续期用）。

优先 `DINGDA_CAMOUFOX_EXE` 或 `DINGDA_PLUGINS_DIR/camoufox` 下的可执行文件；
否则回退系统 Edge/Chrome。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from crawlers.core.playwright_common import (
    LAUNCH_ARGS,
    apply_stealth,
    async_playwright,
    launch_persistent_chromium,
)
from crawlers.factory import create_channel

logger = logging.getLogger("dingda.sidecar.camoufox")

_CAMOUFOX_EXE_NAMES = (
    "camoufox.exe",
    "Camoufox.exe",
    "firefox.exe",
    "camoufox",
    "camoufox-bin",
    "firefox",
)


def resolve_camoufox_executable() -> Path | None:
    """解析本机 Camoufox 可执行文件路径。

    @returns 存在则返回 Path，否则 None
    """
    env = (os.getenv("DINGDA_CAMOUFOX_EXE") or "").strip()
    if env:
        path = Path(env)
        if path.is_file():
            return path
        logger.warning("DINGDA_CAMOUFOX_EXE 无效: %s", env)

    plugins = (os.getenv("DINGDA_PLUGINS_DIR") or "").strip()
    if not plugins:
        return None
    root = Path(plugins) / "camoufox"
    if not root.is_dir():
        return None
    return _find_exe(root)


def _find_exe(directory: Path) -> Path | None:
    for name in _CAMOUFOX_EXE_NAMES:
        direct = directory / name
        if direct.is_file():
            return direct
    try:
        names_lower = {n.lower() for n in _CAMOUFOX_EXE_NAMES}
        for child in directory.rglob("*"):
            if child.is_file() and child.name.lower() in names_lower:
                return child
    except OSError:
        return None
    return None


def _infer_ff_version(executable: Path) -> int:
    """从插件目录的 application.ini / platform.ini 推断主版本号。

    camoufox 包在未传 ``ff_version`` 时会调用 ``installed_verstr()``，去查
    其自管目录 ``official/stable``；我们用插件 zip 解压出的二进制时必须显式传入，
    否则会报 “official/stable is not installed”。

    @param executable Camoufox 可执行文件路径
    @returns Firefox 主版本（如 152）；读不到则回退 152
    """
    import re

    root = executable.parent
    for name in ("application.ini", "platform.ini"):
        ini = root / name
        if not ini.is_file():
            continue
        try:
            text = ini.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = re.search(r"(?mi)^\s*Version\s*=\s*(\d+)", text)
        if match:
            return int(match.group(1))
    return 152


async def launch_renew_context(
    *,
    user_data_dir: Path,
    headless: bool,
    platform_name: str = "xianyu",
) -> tuple[Any, Any, Any, str]:
    """启动续期用浏览器上下文。

    @param user_data_dir 持久化目录
    @param headless 是否无头
    @param platform_name 平台标识
    @returns (playwright_or_none, browser_or_cm, context, engine)
      engine 为 ``camoufox`` 或 ``chromium``。
      Camoufox 时 browser_or_cm 为 AsyncCamoufox 实例（用于 __aexit__）。
    """
    camoufox_exe = resolve_camoufox_executable()
    if camoufox_exe is not None:
        try:
            from camoufox.addons import DefaultAddons
            from camoufox.async_api import AsyncCamoufox
        except ImportError:
            logger.warning("camoufox 包未安装，回退 Chromium")
        else:
            ff_version = _infer_ff_version(camoufox_exe)
            logger.info(
                "使用 Camoufox 启动续期会话 path=%s ff_version=%s",
                camoufox_exe,
                ff_version,
            )
            user_data_dir.mkdir(parents=True, exist_ok=True)
            import sys

            fingerprint_os = (
                "windows"
                if sys.platform == "win32"
                else ("macos" if sys.platform == "darwin" else "linux")
            )
            # 滑块轨迹由我们自己生成；关掉包内 humanize，否则每步 mouse.move
            # 可能被拉到 ~1.5s，容器内/超出轨迹会拖成数分钟。
            cm = AsyncCamoufox(
                executable_path=str(camoufox_exe),
                headless=headless,
                humanize=False,
                persistent_context=True,
                user_data_dir=str(user_data_dir),
                locale="zh-CN",
                os=fingerprint_os,
                ff_version=ff_version,
                i_know_what_im_doing=True,
                exclude_addons=[DefaultAddons.UBO],
            )
            context = await cm.__aenter__()
            return None, cm, context, "camoufox"

    if async_playwright is None:
        msg = "playwright 未安装：请运行 uv add playwright 并执行 playwright install chromium"
        raise RuntimeError(msg)

    browser = create_channel(platform_name).browser()
    user_agent = browser.resolve_user_agent()
    proxy = browser.resolve_proxy()
    playwright = await async_playwright().start()
    launch_kwargs: dict[str, Any] = {
        "headless": headless,
        "args": list(LAUNCH_ARGS),
        "ignore_default_args": ["--enable-automation"],
        "viewport": {"width": 1280, "height": 720},
        "user_agent": user_agent,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }
    if proxy:
        launch_kwargs["proxy"] = proxy
    user_data_dir.mkdir(parents=True, exist_ok=True)
    context = await launch_persistent_chromium(playwright, user_data_dir, **launch_kwargs)
    await apply_stealth(context, logger)
    await browser.apply_anti_detect(context, logger)
    logger.info("使用 Chromium 启动续期会话")
    return playwright, None, context, "chromium"


async def close_renew_session(
    *,
    playwright: Any | None,
    browser_or_cm: Any | None,
    context: Any | None,
    engine: str,
) -> None:
    """关闭续期会话（兼容 Camoufox / Chromium）。

    @param playwright Chromium 路径下的 Playwright 实例
    @param browser_or_cm Camoufox 的 AsyncCamoufox 实例
    @param context 浏览器上下文
    @param engine ``camoufox`` 或 ``chromium``
    """
    import contextlib

    if engine == "camoufox" and browser_or_cm is not None:
        with contextlib.suppress(Exception):
            await browser_or_cm.__aexit__(None, None, None)
        return

    if context is not None:
        with contextlib.suppress(Exception):
            await context.close()
    if playwright is not None:
        with contextlib.suppress(Exception):
            await playwright.stop()
