"""Camoufox 插头：通用 launch / context / page，无平台业务。"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, ClassVar, Mapping, Sequence

from src.browser.context import ContextOptions, proxy_server
from src.browser.page import PlaywrightPage
from src.browser.port import BrowserPort, Cookie, LaunchOptions, Page

logger = logging.getLogger("dingda.browser.camoufox")


def _require_camoufox() -> None:
    try:
        import camoufox  # noqa: F401
    except ImportError as exc:
        raise ImportError("未安装 camoufox，请执行：uv sync") from exc


def _fingerprint_os(profile: str | None) -> str:
    if profile in {"windows", "macos", "linux"}:
        return profile
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


class CamoufoxAdapter(BrowserPort):
    """Camoufox 反检测浏览器插头。"""

    engine: ClassVar[str] = "camoufox"

    def __init__(self) -> None:
        self._cm: Any | None = None
        self._root: Any | None = None  # 浏览器进程，或持久化 context
        self._options = LaunchOptions()
        self._persistent = False

    async def launch(self, options: LaunchOptions | None = None) -> None:
        """启动 Camoufox。"""
        if self._root is not None:
            return
        _require_camoufox()
        from camoufox.addons import DefaultAddons
        from camoufox.async_api import AsyncCamoufox

        self._options = options or LaunchOptions()
        fingerprint_os = _fingerprint_os(self._options.fingerprint_profile)
        self._persistent = self._options.user_data_dir is not None
        started = time.perf_counter()
        # 真正拉起 Firefox/Camoufox 进程，下面耗时通常是大头
        logger.info(
            "Camoufox 开始启动 headless=%s persistent=%s os=%s",
            self._options.headless,
            self._persistent,
            fingerprint_os,
        )

        kwargs: dict[str, Any] = {
            "headless": self._options.headless,
            "humanize": False,
            "locale": self._options.locale,
            "os": fingerprint_os,
            "i_know_what_im_doing": True,
            "exclude_addons": [DefaultAddons.UBO],
        }
        from src.browser.camoufox_bin import resolve_camoufox_exe

        exe = resolve_camoufox_exe()
        if exe is not None:
            kwargs["executable_path"] = str(exe)
        proxy = proxy_server(self._options.proxy_url)
        if proxy:
            kwargs["proxy"] = proxy
        if self._persistent:
            assert self._options.user_data_dir is not None
            self._options.user_data_dir.mkdir(parents=True, exist_ok=True)
            kwargs["persistent_context"] = True
            kwargs["user_data_dir"] = str(self._options.user_data_dir)

        self._cm = AsyncCamoufox(**kwargs)
        try:
            self._root = await self._cm.__aenter__()
        except Exception:
            elapsed = time.perf_counter() - started
            logger.warning(
                "Camoufox 启动失败 elapsed=%.2fs elapsed_ms=%d",
                elapsed,
                int(elapsed * 1000),
            )
            self._cm = None
            raise
        elapsed = time.perf_counter() - started
        logger.info(
            "Camoufox 启动完成 elapsed=%.2fs elapsed_ms=%d",
            elapsed,
            int(elapsed * 1000),
        )

    async def open(
        self,
        *,
        proxy: str | None = None,
        fingerprint: str | None = None,
        cookies: Sequence[Cookie] | Mapping[str, str] | None = None,
        default_domain: str = "",
    ) -> Page:
        """打开一页；非 persistent 时每次新建 context。"""
        if self._root is None:
            await self.launch(
                LaunchOptions(
                    headless=self._options.headless,
                    proxy_url=proxy or self._options.proxy_url,
                    fingerprint_profile=fingerprint or self._options.fingerprint_profile,
                    user_data_dir=self._options.user_data_dir,
                    locale=self._options.locale,
                )
            )

        opts = ContextOptions(
            proxy_url=proxy or self._options.proxy_url,
            fingerprint_profile=fingerprint or self._options.fingerprint_profile,
            cookies=cookies,
            default_cookie_domain=default_domain,
            locale=self._options.locale,
        )
        logger.info(
            "Camoufox 打开页面 proxy=%s fingerprint=%s",
            bool(opts.proxy_url),
            opts.fingerprint_profile,
        )

        if self._persistent:
            page = await self._root.new_page()
            wrapped = PlaywrightPage(page, context=self._root, owns_context=False)
        else:
            ctx_kwargs: dict[str, Any] = {
                "locale": opts.locale,
                "viewport": {
                    "width": opts.viewport_width,
                    "height": opts.viewport_height,
                },
            }
            proxy_opt = proxy_server(opts.proxy_url)
            if proxy_opt:
                ctx_kwargs["proxy"] = proxy_opt
            context = await self._root.new_context(**ctx_kwargs)
            page = await context.new_page()
            wrapped = PlaywrightPage(page, context=context, owns_context=True)

        if cookies:
            # Firefox/Camoufox：空白页直接 add_cookies 常不生效，先落到各 cookie 域名再注入。
            from src.browser.context import normalize_cookies

            normalized = normalize_cookies(cookies, default_domain=default_domain)
            seed_hosts: set[str] = set()
            for item in normalized:
                host = (item.domain or default_domain or "").lstrip(".").strip()
                if host:
                    seed_hosts.add(host)
            for host in sorted(seed_hosts):
                seed = f"https://www.{host}/"
                try:
                    await wrapped.goto(seed, wait_until="domcontentloaded", timeout_ms=25_000)
                except Exception:  # noqa: BLE001
                    logger.debug("Camoufox seed goto failed url=%s", seed, exc_info=True)
            # 清掉 seed 时站点下发的匿名 cookie，再写入账号 cookie，避免冲掉登录态
            try:
                await wrapped.context.clear_cookies()
            except Exception:  # noqa: BLE001
                logger.debug("Camoufox clear_cookies failed", exc_info=True)
            await wrapped.add_cookies(cookies, default_domain=default_domain)
            logger.info(
                "Camoufox 已注入 Cookie count=%s seeds=%s",
                len(normalized),
                sorted(seed_hosts),
            )
            # 注入后再进一遍各域名，页面带着 cookie 重新加载
            for host in sorted(seed_hosts):
                seed = f"https://www.{host}/"
                try:
                    await wrapped.goto(seed, wait_until="domcontentloaded", timeout_ms=25_000)
                except Exception:  # noqa: BLE001
                    logger.debug("Camoufox cookie refresh goto failed url=%s", seed, exc_info=True)
            logger.info("Camoufox Cookie 注入后已刷新 seeds=%s", sorted(seed_hosts))
        return wrapped

    async def close(self) -> None:
        """关闭 Camoufox。"""
        logger.info("Camoufox 正在关闭")
        cm = self._cm
        self._cm = None
        self._root = None
        if cm is not None:
            await cm.__aexit__(None, None, None)
