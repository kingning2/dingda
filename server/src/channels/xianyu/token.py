"""闲鱼 IM accessToken 获取与缓存。

职责：
    调用 mtop.taobao.idlemessage.pc.login.token；按 unb 缓存到产品数据目录，
    供 WebSocket /reg 鉴权，降低敏感接口调用频率。

设计说明：
    - 平台：闲鱼（xianyu）
    - 调用方：channels/xianyu/ws、message
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from src.channels.xianyu.mtop import call as mtop_call
from src.channels.xianyu.session import Session
from src.shared.errors import AppError

logger = logging.getLogger("dingda.channel.xianyu.token")

IM_APP_KEY = "444e9908a51d1cb236a27862abc769c9"
DEFAULT_TTL = 30 * 60


def _ttl() -> int:
    try:
        return max(60, int(os.environ.get("DINGDA_IM_TOKEN_TTL", DEFAULT_TTL)))
    except ValueError:
        return DEFAULT_TTL


def _cache_path() -> Path:
    from src.infrastructure.db.session import data_dir

    return data_dir() / "xianyu" / "token.json"


def _load_cache(unb: str) -> str | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if raw.get("unb") != unb:
        return None
    if time.time() - float(raw.get("t", 0)) > _ttl():
        return None
    return raw.get("token") or None


def _save_cache(unb: str, token: str) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"unb": unb, "token": token, "t": time.time()}),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("写入 token 缓存失败: %s", exc)


def get_access_token(session: Session, *, force_refresh: bool = False) -> str:
    """取 WebSocket 用的 accessToken。"""
    env_token = os.environ.get("DINGDA_IM_TOKEN", "").strip()
    if env_token:
        return env_token
    if not force_refresh:
        cached = _load_cache(session.unb)
        if cached:
            return cached
    raw = mtop_call(
        session,
        api="mtop.taobao.idlemessage.pc.login.token",
        data={"appKey": IM_APP_KEY, "deviceId": session.device_id},
        version="1.0",
        spm_cnt="a21ybx.im.0.0",
        auto_refresh=False,
    )
    token = (raw.get("data") or {}).get("accessToken", "")
    if not token:
        raise AppError(
            "account.session_expired",
            f"accessToken 获取失败：{raw.get('ret')}",
            status_code=401,
        )
    _save_cache(session.unb, token)
    logger.info("im accessToken 已刷新 unb=%s", session.unb)
    return token


def refresh_login(session: Session) -> dict[str, Any]:
    """轻量 ping，长连保活用。"""
    return mtop_call(
        session,
        api="mtop.taobao.idlemessage.pc.loginuser.get",
        data={},
        version="1.0",
        spm_cnt="a21ybx.im.0.0",
        auto_refresh=False,
    )
