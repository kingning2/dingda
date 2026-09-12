"""闲鱼登录态续期与轻量探活。

职责：
    refresh：无头页点「快速进入」续 cookie；token / probe / profile：HTTP 探活或拉资料，
    失败再走 browser.sync 浏览器续期。

设计说明：
    - 平台：闲鱼（xianyu）
    - 调用方：扫码登录（一次拉昵称头像）、domains/account token_scheduler、mtop 登录态失效重试
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from browser.sync import run_on_sync_browser, sync_headless_page
from channels.cookie_header import cookie_header, parse_cookie_header
from channels.xianyu.cookies import cookie_map, to_browser_cookies
from channels.xianyu.mtop import call as mtop_call
from channels.xianyu.session import Session
from core.errors import AppError

logger = logging.getLogger("dingda.channel.xianyu.refresh")

_HOME_URL = "https://www.goofish.com"
_AUTH_PROBE_URL = "https://www.goofish.com/bought"
_REQUIRED_COOKIES = ("_m_h5_tk", "unb", "cookie2")
_LOGIN_API = "mtop.taobao.idlemessage.pc.loginuser.get"
_PROFILE_API = "mtop.idle.web.user.page.nav"


@dataclass(frozen=True)
class XianyuNavProfile:
    """闲鱼个人主页（user.page.nav module.base）。"""

    display_name: str | None = None
    avatar_url: str | None = None
    followers: int | None = None
    following: int | None = None
    sold_count: int | None = None
    purchase_count: int | None = None
    collection_count: int | None = None


def _try_quick_enter(page: Any) -> bool:
    """闲鱼首页 passport 弹窗点「快速进入」免密续期。"""
    iframe_el = page.query_selector("#alibaba-login-box")
    if not iframe_el:
        return True
    frame = iframe_el.content_frame()
    if not frame:
        logger.debug("alibaba-login-box iframe 未就绪")
        return False
    try:
        frame.wait_for_load_state("domcontentloaded", timeout=5_000)
        page.wait_for_timeout(800)
        frame.get_by_text("快速进入", exact=True).first.click(timeout=5_000)
        logger.info("已点击闲鱼「快速进入」")
        page.wait_for_selector("#alibaba-login-box", state="hidden", timeout=10_000)
        return True
    except Exception as exc:
        logger.warning("闲鱼「快速进入」不可用: %s", exc)
        return False


def refresh(cookies: dict[str, str]) -> dict[str, str]:
    """用无头页访问闲鱼续期 cookie。"""
    logger.info("refresh start")

    def _job() -> dict[str, str]:
        with sync_headless_page(cookies=to_browser_cookies(cookies)) as page:
            page.goto(_HOME_URL, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(1500)
            if not _try_quick_enter(page):
                return {}
            try:
                page.goto(_AUTH_PROBE_URL, wait_until="domcontentloaded", timeout=15_000)
                page.wait_for_timeout(1500)
            except Exception as exc:
                logger.debug("访问 /bought 异常（忽略）: %s", exc)
            return cookie_map(page.context.cookies())

    fresh = run_on_sync_browser(_job)
    missing = [key for key in _REQUIRED_COOKIES if key not in fresh]
    if missing:
        logger.warning("续期后仍缺 cookie: %s", ", ".join(missing))
        return {}
    logger.info("refresh done")
    return fresh


def _prepare_session(cookie: str) -> Session:
    cookies = parse_cookie_header(cookie)
    missing = [key for key in _REQUIRED_COOKIES if not cookies.get(key)]
    if missing:
        raise ValueError(f"cookie 缺字段: {', '.join(missing)}")
    return Session.from_cookie_header(cookie)


def _ping_login(session: Session, *, auto_refresh: bool = False) -> dict:
    return mtop_call(
        session,
        api=_LOGIN_API,
        data={},
        version="1.0",
        spm_cnt="a21ybx.im.0.0",
        auto_refresh=auto_refresh,
    )


def probe(cookie: str) -> bool:
    """轻量 HTTP 探活（不启浏览器）。调度器启动探活请用 ``token``，可静默续期。"""
    if not cookie.strip():
        return False
    try:
        session = _prepare_session(cookie)
        _ping_login(session, auto_refresh=False)
        return True
    except Exception as exc:
        logger.debug("闲鱼 HTTP 探活失败: %s", exc)
        return False


def profile(cookie: str) -> tuple[str | None, str | None]:
    """HTTP 拉取闲鱼昵称与头像（``mtop.idle.web.user.page.nav``）。"""
    try:
        page = nav_profile(cookie)
    except Exception as exc:
        logger.info("闲鱼资料 API 失败: %s", exc)
        return None, None
    return page.display_name, page.avatar_url


def nav_profile(cookie: str) -> XianyuNavProfile:
    """拉取闲鱼个人主页字段；cookie 无效或接口失败抛错。"""
    if not cookie.strip():
        raise AppError("account.no_cookie", "账号缺少登录信息", status_code=400)
    try:
        session = _prepare_session(cookie)
    except ValueError as exc:
        raise AppError("account.session_expired", str(exc), status_code=401) from exc
    raw = mtop_call(
        session,
        api=_PROFILE_API,
        data={},
        version="1.0",
        auto_refresh=False,
    )
    page = _profile_from_nav(raw)
    logger.info(
        "nav_profile done name=%s avatar=%s followers=%s",
        bool(page.display_name),
        bool(page.avatar_url),
        page.followers,
    )
    return page


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _profile_from_nav(raw: dict[str, Any]) -> XianyuNavProfile:
    """从 user.page.nav 响应抽出个人主页字段（对齐 main sidecar）。"""
    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        return XianyuNavProfile()
    module = data.get("module")
    base = module.get("base") if isinstance(module, dict) else None
    if not isinstance(base, dict):
        return XianyuNavProfile()
    name = str(base.get("displayName") or "").strip() or None
    avatar = str(base.get("avatar") or "").strip() or None
    return XianyuNavProfile(
        display_name=name,
        avatar_url=avatar,
        followers=_as_int(base.get("followers")),
        following=_as_int(base.get("following")),
        sold_count=_as_int(base.get("soldCount")),
        purchase_count=_as_int(base.get("purchaseCount")),
        collection_count=_as_int(base.get("collectionCount")),
    )


def status(cookie: str) -> dict[str, Any]:
    """检查登录态，返回 unb / tracknick / nick / valid。"""
    session = Session.from_cookie_header(cookie)
    try:
        raw = _ping_login(session, auto_refresh=False)
        user = raw.get("data", {}) or {}
        logger.info("status ok unb=%s", session.unb)
        return {
            "unb": session.unb,
            "tracknick": session.tracknick,
            "nick": user.get("nick", ""),
            "valid": True,
        }
    except Exception as exc:
        logger.info("status invalid: %s", exc)
        return {
            "unb": session.unb,
            "tracknick": session.tracknick,
            "nick": "",
            "valid": False,
            "error": str(exc),
        }


def token(cookie: str) -> tuple[str, bool]:
    """探活并尽量续期：先 ``loginuser.get``，失败再浏览器「快速进入」续 cookie。

    返回 ``(cookie, ok)``：``ok=True`` 表示登录仍可用（cookie 可能已更新）；
    ``ok=False`` 才表示需重新扫码。
    """
    try:
        session = _prepare_session(cookie)
    except (ValueError, AppError) as exc:
        logger.info("闲鱼 %s，跳过刷新", exc)
        return cookie, False

    unb = session.unb
    try:
        try:
            _ping_login(session, auto_refresh=False)
        except Exception as exc:
            logger.info("闲鱼 HTTP 探活失败，尝试浏览器静默续期: %s", exc)
            fresh = refresh(session.http.cookies.get_dict())
            if not fresh:
                raise
            session.sync_cookies(fresh)
            _ping_login(session, auto_refresh=False)

        refreshed = cookie_header(session.http.cookies.get_dict())
        changed = refreshed.strip() != cookie.strip()
        if changed:
            logger.info("闲鱼 token 已刷新: unb=%s", unb)
        else:
            logger.debug("闲鱼 token 刷新完成（cookie 未变）: unb=%s", unb)
        return refreshed, True
    except Exception as exc:
        logger.warning("闲鱼 token 刷新失败: %s", exc)
        return cookie, False
