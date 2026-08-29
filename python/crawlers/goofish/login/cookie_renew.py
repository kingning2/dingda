"""闲鱼 Cookie 浏览器续期：风控 / 验证码时临时启动 Playwright。

对齐 xianyu-auto-reply：
- 稳态不常驻浏览器；
- 风控页优先自动拖滑块；
- 自动失败再回退有头人工完成。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from crawlers.core.camoufox import close_renew_session, launch_renew_context
from crawlers.core.platform_config import get_platform_config, normalize_platform
from crawlers.core.playwright_common import (
    async_playwright,
    clear_profile_locks,
    to_serializable_cookies,
)
from crawlers.core.slider import (
    auto_slider_enabled,
    clear_risk_cookies,
    has_x5sec,
    try_solve_slider,
)

logger = logging.getLogger("dingda.sidecar.cookie-renew")

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
DEFAULT_TIMEOUT_SECS = 180
GOOFISH_DOMAIN = ".goofish.com"

# 续期回写时保留的 Cookie 域（过宽会把淘宝杂 Cookie 拼进 Header，易触发非法请求）。
_RENEW_COOKIE_DOMAINS = (
    "goofish.com",
    "taobao.com",
    "alibaba.com",
    "alipay.com",
    "mmstat.com",
    "alicdn.com",
)

# 同名 Cookie 优先保留这些域上的值（闲鱼会话）。
_PREFERRED_COOKIE_DOMAINS = ("goofish.com", "taobao.com")


def _safe_account_dir(account_id: str) -> str:
    """把账号 id 收成可作目录名的片段。"""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", account_id.strip()) or "unknown"
    return cleaned[:80]


def _playwright_cookie(raw: dict[str, Any]) -> dict[str, Any] | None:
    """把契约 Cookie 转成 Playwright add_cookies 入参。"""
    name = str(raw.get("name") or "").strip()
    value = str(raw.get("value") or "").strip()
    if not name or not value:
        return None
    domain = str(raw.get("domain") or "").strip() or GOOFISH_DOMAIN
    if domain.startswith("http"):
        domain = GOOFISH_DOMAIN
    path = str(raw.get("path") or "").strip() or "/"
    cookie: dict[str, Any] = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
    }
    http_only = raw.get("httpOnly")
    if http_only is None:
        http_only = raw.get("http_only")
    if isinstance(http_only, bool):
        cookie["httpOnly"] = http_only
    if isinstance(raw.get("secure"), bool):
        cookie["secure"] = raw["secure"]
    same_site = raw.get("sameSite") or raw.get("same_site")
    if isinstance(same_site, str) and same_site:
        cookie["sameSite"] = same_site
    expires = raw.get("expires")
    if isinstance(expires, (int, float)) and expires > 0:
        cookie["expires"] = expires
    return cookie


def _looks_logged_in(page_url: str, cookies: list[dict[str, Any]], login_cookie: str) -> bool:
    """用 Cookie 与当前 URL 判断是否仍保持登录。"""
    has_unb = any(c.get("name") == login_cookie for c in cookies)
    has_tk = any(c.get("name") == "_m_h5_tk" for c in cookies)
    url = page_url.lower()
    blocked = any(token in url for token in ("punish", "captcha", "_____tmd_____", "passport"))
    # 滑块通过后可能仍短暂停在 punish 页，但已有 x5sec
    if has_unb and has_tk and has_x5sec(cookies):
        return True
    return has_unb and has_tk and not blocked


def _resolve_headless(*, has_punish: bool, force_headed: bool, try_auto: bool = False) -> bool:
    """解析是否无头。

    默认无头（不弹窗）；人工回退（force_headed）始终有头。
    设 DINGDA_COOKIE_RENEW_HEADLESS=0 可强制有头调试。

    @param has_punish 是否带 punish URL（保留参数，兼容调用方）
    @param force_headed 人工滑块回退时强制有头
    @param try_auto 是否自动滑块路径（保留参数，兼容调用方）
    """
    del has_punish, try_auto
    if force_headed:
        return False
    env = os.getenv("DINGDA_COOKIE_RENEW_HEADLESS", "1").strip().lower()
    return env not in {"0", "false", "no", "off"}


def _has_cookie(cookies: list[dict[str, Any]], name: str) -> bool:
    """是否存在指定名称的 Cookie。"""
    return any(c.get("name") == name for c in cookies)


def _domain_rank(domain: str) -> int:
    """域优先级：数字越小越优先。"""
    lowered = (domain or "").lower()
    for index, preferred in enumerate(_PREFERRED_COOKIE_DOMAINS):
        if preferred in lowered:
            return index
    return 100


def _is_renew_domain(domain: str) -> bool:
    """是否属于闲鱼续期可回写的域。"""
    lowered = (domain or "").lower()
    return any(item in lowered for item in _RENEW_COOKIE_DOMAINS)


def _dedupe_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 name 去重，优先保留 goofish / taobao 域。"""
    best: dict[str, dict[str, Any]] = {}
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        if not name or not cookie.get("value"):
            continue
        domain = str(cookie.get("domain") or "")
        previous = best.get(name)
        if previous is None or _domain_rank(domain) < _domain_rank(
            str(previous.get("domain") or "")
        ):
            best[name] = cookie
    return list(best.values())


def _filter_export_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """过滤并去重导出 Cookie，避免整库杂 Cookie 导致 mtop 非法请求。"""
    filtered = [
        cookie
        for cookie in cookies
        if _is_renew_domain(str(cookie.get("domain") or ""))
        or str(cookie.get("name") or "")
        in {
            "unb",
            "_m_h5_tk",
            "_m_h5_tk_enc",
            "cookie2",
            "cna",
            "x5sec",
            "XSRF-TOKEN",
            "sgcookie",
            "tfstk",
            "isg",
        }
    ]
    if not filtered:
        filtered = list(cookies)
    return _dedupe_cookies(filtered)


def _merge_prepared_with_browser(
    prepared: list[dict[str, Any]],
    browser_cookies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """以原账号 Cookie 为底，叠浏览器侧闲鱼相关更新（含 x5sec / _m_h5_tk）。

    Camoufox 会话常夹带淘宝全站 Cookie；直接全量回写会让 Rust Chrome 指纹请求
    变成 ``FAIL_SYS_ILLEGAL_ACCESS``。这里只合并必要字段。
    """
    merged: dict[str, dict[str, Any]] = {}
    for cookie in prepared:
        name = str(cookie.get("name") or "").strip()
        if name and cookie.get("value"):
            merged[name] = cookie
    for cookie in _filter_export_cookies(browser_cookies):
        name = str(cookie.get("name") or "").strip()
        if name and cookie.get("value"):
            merged[name] = cookie
    return list(merged.values())


async def _export_after_slider(
    *,
    page: Any,
    context: Any,
    config: Any,
    account_id: str,
    prepared: list[dict[str, Any]],
) -> tuple[bool, str, dict[str, Any]]:
    """滑块通过后：回闲鱼首页刷新 ``_m_h5_tk``，再合并导出供 Rust 回写。

    阿里风控通过后常会跳到淘宝 / passport；不能跟着停在淘宝。

    @param page 当前页
    @param context 浏览器上下文
    @param config 平台登录配置
    @param account_id 账号 id（日志）
    @param prepared 续期前注入的原 Cookie
    @returns (成功, 说明, {status, cookies})
    """
    await page.wait_for_timeout(500)
    raw = to_serializable_cookies(await context.cookies())
    logger.info(
        "滑块后 Cookie 快照 account=%s raw=%s x5sec=%s unb=%s url=%s",
        account_id,
        len(raw),
        has_x5sec(raw),
        _has_cookie(raw, config.login_cookie_name),
        (page.url or "")[:160],
    )

    # 强制回到闲鱼首页（最多 3 次），刷新 h5 签名 token。
    for attempt in range(1, 4):
        current = (page.url or "").lower()
        on_goofish = config.cookie_domain_keyword in current and "passport" not in current
        if not on_goofish:
            logger.info(
                "滑块后回访闲鱼首页 account=%s attempt=%s from=%s",
                account_id,
                attempt,
                current[:160],
            )
            try:
                await page.goto(
                    config.home_url,
                    wait_until="domcontentloaded",
                    timeout=40000,
                )
                await page.wait_for_timeout(3000)
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "回访闲鱼首页失败 account=%s attempt=%s error=%s",
                    account_id,
                    attempt,
                    error,
                )
                continue

        raw = to_serializable_cookies(await context.cookies())
        exported = _merge_prepared_with_browser(prepared, raw)
        has_login = _has_cookie(exported, config.login_cookie_name)
        has_tk = _has_cookie(exported, "_m_h5_tk")
        names = sorted({str(c.get("name")) for c in exported if c.get("name")})
        logger.info(
            "回访后 Cookie account=%s exported=%s unb=%s _m_h5_tk=%s x5sec=%s names=%s url=%s",
            account_id,
            len(exported),
            has_login,
            has_tk,
            has_x5sec(exported),
            ",".join(names[:40]),
            (page.url or "")[:160],
        )

        # 必须同时有登录态与签名 token，否则 Rust token 接口会非法请求。
        if has_login and has_tk:
            return (
                True,
                "自动滑块通过，已导出 Cookie",
                {"status": STATUS_SUCCESS, "cookies": exported},
            )

        # 缺 _m_h5_tk：再点一次首页触发 mtop。
        if has_login and not has_tk:
            with contextlib.suppress(Exception):
                await page.goto(
                    config.home_url,
                    wait_until="networkidle",
                    timeout=40000,
                )
                await page.wait_for_timeout(2000)

    raw = to_serializable_cookies(await context.cookies())
    exported = _merge_prepared_with_browser(prepared, raw)
    if _has_cookie(exported, config.login_cookie_name) and _has_cookie(exported, "_m_h5_tk"):
        return (
            True,
            "自动滑块通过，已导出 Cookie",
            {"status": STATUS_SUCCESS, "cookies": exported},
        )
    return (
        False,
        "滑块疑似通过但未能导出有效 Cookie（需要 unb + _m_h5_tk）",
        {"status": STATUS_FAILED, "cookies": exported or None},
    )


async def _run_renew_session(
    *,
    prepared: list[dict[str, Any]],
    account_id: str,
    target: str,
    punish: str,
    platform_name: str,
    config: Any,
    timeout_secs: int,
    headless: bool,
    try_auto: bool,
) -> tuple[bool, str, dict[str, Any]]:
    """启动一次浏览器会话并尝试续期。

    @returns (成功, 说明, {status, cookies})
    """
    user_data_dir = Path.cwd() / "browser_data" / f"user_{_safe_account_dir(account_id)}"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    clear_profile_locks(user_data_dir)

    playwright = None
    browser_or_cm = None
    context = None
    engine = "chromium"
    try:
        playwright, browser_or_cm, context, engine = await launch_renew_context(
            user_data_dir=user_data_dir,
            headless=headless,
            platform_name=platform_name,
        )
        with contextlib.suppress(Exception):
            await context.add_cookies(prepared)

        page = context.pages[0] if context.pages else await context.new_page()
        logger.info(
            "开始浏览器续期 account=%s engine=%s headless=%s auto_slider=%s url=%s",
            account_id,
            engine,
            headless,
            try_auto,
            target[:120],
            extra={"event": "channel.cookie_renew.started", "account_id": account_id},
        )
        await page.goto(target, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(1500)
        # 清掉历史 risk cookies，让风控挑战重新开始，避免复用旧的 punish 态
        await clear_risk_cookies(context)

        if try_auto:
            ok, detail = await try_solve_slider(
                page, context, max_retries=3, prefer_page_mouse=(engine == "camoufox")
            )
            logger.info(
                "自动滑块结果 account=%s ok=%s detail=%s url=%s",
                account_id,
                ok,
                detail,
                (page.url or "")[:160],
            )
            if ok:
                return await _export_after_slider(
                    page=page,
                    context=context,
                    config=config,
                    account_id=account_id,
                    prepared=prepared,
                )

        # 人工等待（有头）或自动失败后的兜底轮询
        deadline = time.monotonic() + max(15, timeout_secs)
        last_detail = "等待页面登录态稳定"
        if punish and not headless:
            last_detail = "请在弹出的浏览器窗口完成滑块验证"
            logger.info(
                "等待人工完成滑块 account=%s",
                account_id,
            )

        while time.monotonic() < deadline:
            raw = to_serializable_cookies(await context.cookies())
            exported = _merge_prepared_with_browser(prepared, raw)
            url = page.url
            if _looks_logged_in(url, exported, config.login_cookie_name):
                if ("punish" in url.lower() or "captcha" in url.lower()) and not has_x5sec(
                    exported
                ):
                    last_detail = "仍在验证码页，请完成滑块"
                    await page.wait_for_timeout(1500)
                    continue
                if "goofish.com" not in url.lower():
                    with contextlib.suppress(Exception):
                        await page.goto(
                            config.home_url,
                            wait_until="domcontentloaded",
                            timeout=40000,
                        )
                        await page.wait_for_timeout(2000)
                    raw = to_serializable_cookies(await context.cookies())
                    exported = _merge_prepared_with_browser(prepared, raw)
                if not _has_cookie(exported, "_m_h5_tk"):
                    last_detail = "已登录但缺少 _m_h5_tk，继续等待首页会话"
                    await page.wait_for_timeout(1500)
                    continue
                logger.info(
                    "浏览器续期成功 account=%s cookies=%s",
                    account_id,
                    len(exported),
                    extra={"event": "channel.cookie_renew.completed", "account_id": account_id},
                )
                return (
                    True,
                    "浏览器续期成功，已导出 Cookie",
                    {"status": STATUS_SUCCESS, "cookies": exported},
                )
            last_detail = "请在弹出的浏览器窗口完成验证码或登录"
            await page.wait_for_timeout(1500)

        return False, f"浏览器续期超时：{last_detail}", {"status": STATUS_FAILED}
    except Exception as error:  # noqa: BLE001
        logger.exception(
            "浏览器续期失败 account=%s",
            account_id,
            extra={"event": "channel.cookie_renew.failed", "account_id": account_id},
        )
        return False, f"浏览器续期失败: {error}", {"status": STATUS_FAILED}
    finally:
        await close_renew_session(
            playwright=playwright,
            browser_or_cm=browser_or_cm,
            context=context,
            engine=engine,
        )
        await asyncio.sleep(0.05)


async def renew_cookies(
    cookies: list[dict[str, Any]],
    *,
    account_id: str,
    punish_url: str | None = None,
    platform: str = "xianyu",
    timeout_secs: int = DEFAULT_TIMEOUT_SECS,
) -> tuple[bool, str, dict[str, Any]]:
    """注入现有 Cookie，优先自动过滑块，失败再有头人工。

    @param cookies 现有 Cookie 列表（契约 ChannelCookie）
    @param account_id 账号 id（用于持久化目录）
    @param punish_url 风控惩罚页；空则打开闲鱼首页
    @param platform 平台标识
    @param timeout_secs 最长等待秒数（人工回退阶段）
    @returns (成功, 说明, {status, cookies})
    """
    if async_playwright is None:
        msg = "playwright 未安装：请运行 uv add playwright 并执行 playwright install chromium"
        return False, msg, {"status": STATUS_FAILED}

    platform_name = normalize_platform(platform)
    config = get_platform_config(platform_name)
    prepared = [item for item in (_playwright_cookie(raw) for raw in cookies) if item]
    if not prepared:
        return False, "没有可注入的 Cookie，请先扫码或密码登录", {"status": STATUS_FAILED}

    punish = (punish_url or "").strip()
    target = punish or config.home_url
    want_auto = auto_slider_enabled()

    # 1) 自动滑块（默认有头；不强制要求 punish URL）
    if want_auto:
        headless = _resolve_headless(has_punish=bool(punish), force_headed=False, try_auto=True)
        ok, detail, data = await _run_renew_session(
            prepared=prepared,
            account_id=account_id,
            target=target,
            punish=punish,
            platform_name=platform_name,
            config=config,
            timeout_secs=min(60, timeout_secs),
            headless=headless,
            try_auto=True,
        )
        if ok:
            return ok, detail, data
        logger.warning(
            "自动滑块未通过，回退有头人工 account=%s detail=%s",
            account_id,
            detail,
        )

    # 2) 有头人工 / 关闭自动时的普通续期
    headless = _resolve_headless(has_punish=bool(punish), force_headed=True, try_auto=False)
    return await _run_renew_session(
        prepared=prepared,
        account_id=account_id,
        target=target,
        punish=punish,
        platform_name=platform_name,
        config=config,
        timeout_secs=timeout_secs,
        headless=headless,
        try_auto=False,
    )
