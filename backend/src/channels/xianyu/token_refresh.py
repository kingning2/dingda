"""闲鱼 _m_h5_tk 定时刷新（HTTP ping + Camoufox 续期）。"""

from __future__ import annotations

import logging

from src.channels.profile_fields import extract_profile_from_tree
from src.adapters.channel.camoufox_browser import refresh_xianyu_cookies
from src.adapters.crawler.goofish import get_goofish_session_factory
from src.adapters.registry import is_vendor_installed
from src.channels.cookie_utils import cookie_header, parse_cookie_header

logger = logging.getLogger("dingda.channel.xianyu.token_refresh")

_REQUIRED = ("unb", "_m_h5_tk", "cookie2")


def _device_id(unb: str) -> str:
    from goofish_cli.core.sign import generate_device_id

    return generate_device_id(unb)


def _build_session(cookie: str):
    session_mod = get_goofish_session_factory()
    cookies = parse_cookie_header(cookie)
    http = __import__("requests").Session()
    http.cookies.update(cookies)
    return session_mod.Session(
        http=http,
        unb=cookies["unb"],
        tracknick=cookies.get("tracknick", ""),
        device_id=_device_id(cookies["unb"]),
    )


def _ping_login(session, *, auto_refresh: bool = False) -> None:
    from goofish_cli.core.mtop import call as mtop_call

    mtop_call(
        session,
        api="mtop.taobao.idlemessage.pc.loginuser.get",
        data={},
        version="1.0",
        spm_cnt="a21ybx.im.0.0",
        _auto_refresh=auto_refresh,
    )


def _sync_session_cookies(session, cookies: dict[str, str]) -> None:
    session.http.cookies.clear()
    session.http.cookies.update(cookies)


def _prepare_session(cookie: str):
    cookies = parse_cookie_header(cookie)
    missing = [key for key in _REQUIRED if not cookies.get(key)]
    if missing:
        raise ValueError(f"cookie 缺字段: {', '.join(missing)}")
    return cookies, _build_session(cookie)


def probe_token(cookie: str) -> bool:
    """HTTP 探活（不启动浏览器），用于轻量校验登录态。"""
    if not is_vendor_installed("goofish_cli"):
        return False
    if not cookie.strip():
        return False
    try:
        _cookies, session = _prepare_session(cookie)
        _ping_login(session, auto_refresh=False)
        return True
    except Exception as exc:
        logger.debug("闲鱼 HTTP 探活失败: %s", exc)
        return False


def fetch_user_profile(cookie: str) -> tuple[str | None, str | None]:
    """HTTP 拉取闲鱼昵称与头像（不启动浏览器）。"""
    if not is_vendor_installed("goofish_cli") or not cookie.strip():
        return None, None
    try:
        _cookies, session = _prepare_session(cookie)
    except ValueError as exc:
        logger.debug("闲鱼资料拉取跳过: %s", exc)
        return None, None

    from goofish_cli.core.mtop import call as mtop_call

    try:
        raw = mtop_call(
            session,
            api="mtop.taobao.idlemessage.pc.loginuser.get",
            data={},
            version="1.0",
            spm_cnt="a21ybx.im.0.0",
            _auto_refresh=False,
        )
    except Exception as exc:
        logger.info("闲鱼资料 API 失败: %s", exc)
        return None, None

    data = raw.get("data") if isinstance(raw, dict) else None
    if not isinstance(data, dict):
        return None, None
    return extract_profile_from_tree(data)


def refresh_token(cookie: str) -> tuple[str, bool]:
    """刷新闲鱼 token，返回 (cookie 字符串, 是否成功)。"""
    if not is_vendor_installed("goofish_cli"):
        logger.info("goofish_cli 未安装，跳过闲鱼 token 刷新")
        return cookie, False

    try:
        cookies, session = _prepare_session(cookie)
    except ValueError as exc:
        logger.info("闲鱼 %s，跳过刷新", exc)
        return cookie, False

    unb = cookies["unb"]
    try:
        try:
            _ping_login(session, auto_refresh=False)
        except Exception as exc:
            logger.info("闲鱼 HTTP 刷新失败，尝试 Camoufox 续期: %s", exc)
            fresh = refresh_xianyu_cookies(cookies)
            if not fresh:
                raise
            _sync_session_cookies(session, fresh)
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
