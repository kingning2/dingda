"""闲鱼 mtop HTTP 调用模板。

职责：
    统一 Session headers、query params 与 sign；将风控、签名失败、登录态失效映射为 AppError；
    可选在 session 过期时经 channels 浏览器续 cookie 后重试一次。

设计说明：
    - 平台：闲鱼（xianyu）；本包 category/item/location/token 等均依赖此入口
    - 不直接供 Tool 调用
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from src.channels.xianyu.session import USER_AGENT, Session
from src.channels.xianyu.sign import generate_sign
from src.shared.errors import (
    AppError,
    not_found_error,
    risk_control_error,
    session_expired_error,
    sign_error,
)

logger = logging.getLogger("dingda.channel.xianyu.mtop")

APP_KEY = "34839810"
MTOP_HOST = "https://h5api.m.goofish.com"

_RISK_KEYWORDS = (
    "RGV587_ERROR",
    "FAIL_SYS_USER_VALIDATE",
    "哎哟喂",
    "/punish",
)
_AUTH_KEYWORDS = (
    "FAIL_SYS_SESSION_EXPIRED",
    "FAIL_SYS_TOKEN_EXOIRED",
    "FAIL_SYS_TOKEN_EMPTY",
    "令牌过期",
    "FAIL_SYS_ILLEGAL_ACCESS",
)
_RECOVERABLE_AUTH = (
    "FAIL_SYS_TOKEN_EXOIRED",
    "FAIL_SYS_TOKEN_EMPTY",
    "FAIL_SYS_SESSION_EXPIRED",
    "令牌过期",
)


def default_headers() -> dict[str, str]:
    return {
        "accept": "application/json",
        "accept-language": "en,zh-CN;q=0.9,zh;q=0.8,zh-TW;q=0.7,ja;q=0.6",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.goofish.com",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.goofish.com/",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": USER_AGENT,
    }


def call(
    session: Session,
    api: str,
    data: dict[str, Any] | list[Any] | str,
    *,
    version: str = "1.0",
    spm_cnt: str = "a21ybx.home.0.0",
    extra_params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    auto_refresh: bool = True,
) -> dict[str, Any]:
    """调用 mtop。返回原始 JSON；失败抛 AppError。"""
    url = f"{MTOP_HOST}/h5/{api}/{version}/"
    t_ms = str(int(time.time() * 1000))
    data_val = data if isinstance(data, str) else json.dumps(data, separators=(",", ":"))

    token = session.h5_token
    if not token:
        raise session_expired_error("xianyu")
    sign = generate_sign(t_ms, token, data_val)

    params = {
        "jsv": "2.7.2",
        "appKey": APP_KEY,
        "t": t_ms,
        "sign": sign,
        "v": version,
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": api,
        "sessionOption": "AutoLoginOnly",
        "spm_cnt": spm_cnt,
    }
    if extra_params:
        params.update(extra_params)

    resp = session.http.post(
        url,
        params=params,
        headers=headers or default_headers(),
        data={"data": data_val},
        timeout=30,
    )
    raw = resp.json()
    try:
        _classify_error(raw, api)
    except AppError as exc:
        if not (auto_refresh and _is_recoverable_auth(exc)):
            raise
        if not _try_refresh_cookies(session):
            raise
        return call(
            session,
            api,
            data,
            version=version,
            spm_cnt=spm_cnt,
            extra_params=extra_params,
            headers=headers,
            auto_refresh=False,
        )
    return raw


def _is_recoverable_auth(exc: AppError) -> bool:
    if exc.code != "account.session_expired":
        return False
    return any(kw in exc.message for kw in _RECOVERABLE_AUTH)


def _try_refresh_cookies(session: Session) -> bool:
    """走 channels 的 Camoufox 续期；成功则回写 session。"""
    from src.channels.cookie_header import cookie_header
    from src.channels.xianyu.refresh import refresh

    current = session.http.cookies.get_dict()
    logger.info("mtop 登录态失效，尝试 Camoufox 续期: unb=%s", session.unb)
    fresh = refresh(current)
    if not fresh:
        return False
    session.sync_cookies(fresh)
    logger.info("mtop cookie 续期成功: unb=%s cookie_len=%s", session.unb, len(cookie_header(fresh)))
    return True


def _classify_error(raw: dict[str, Any], api: str) -> None:
    ret = raw.get("ret") or []
    ret_str = " | ".join(ret) if isinstance(ret, list) else str(ret)
    if not ret_str or "SUCCESS" in ret_str:
        return

    for kw in _RISK_KEYWORDS:
        if kw in ret_str:
            raise risk_control_error(f"[{api}] 触发风控：{ret_str}")
    for kw in _AUTH_KEYWORDS:
        if kw in ret_str:
            raise AppError(
                "account.session_expired",
                f"[{api}] 登录态失效：{ret_str}",
                status_code=401,
            )
    if "ILLEGAL_REQUEST" in ret_str or "sign" in ret_str.lower():
        raise sign_error(f"[{api}] 签名错误：{ret_str}")
    if "NOT_FOUND" in ret_str or "不存在" in ret_str:
        raise not_found_error(f"[{api}] 未找到：{ret_str}")
    raise AppError("channel.mtop_failed", f"[{api}] 调用失败：{ret_str}", status_code=502)
