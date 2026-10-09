"""预览浏览器会话端点。

职责：
    商品预览注入用：返回已映射域名的 cookie 与 localStorage。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from contracts.account import (
    AccountPlatform,
    BrowserCookieItem,
    BrowserSessionResponse,
)
from tools.account_cookie import resolve_browser_session

logger = logging.getLogger("dingda.api.account")

router = APIRouter(prefix="/v1/accounts")


@router.get("/browser-session", response_model=BrowserSessionResponse)
def get_browser_session(
    platform: AccountPlatform = Query(..., description="xianyu / xiaohongshu"),
) -> BrowserSessionResponse:
    """商品预览注入用：返回已映射域名的 cookie 与 localStorage。"""
    session = resolve_browser_session(platform)
    if session is None:
        logger.info("browser-session empty platform=%s", platform)
        return BrowserSessionResponse(
            ok=False,
            platform=platform,
            message="未找到可用登录账号，将以未登录态打开",
        )
    cookies = [
        BrowserCookieItem(
            name=item.name,
            value=item.value,
            domain=item.domain,
            path=item.path or "/",
            secure=bool(item.secure),
            http_only=bool(item.http_only),
            same_site=item.same_site or "Lax",
            expires=float(item.expires) if item.expires is not None else None,
        )
        for item in session.cookies
    ]
    logger.info(
        "browser-session ok platform=%s account=%s cookies=%s ls=%s",
        platform,
        session.account_id,
        len(cookies),
        len(session.local_storage),
    )
    return BrowserSessionResponse(
        ok=True,
        platform=platform,  # type: ignore[arg-type]
        account_id=session.account_id,
        cookies=cookies,
        local_storage=session.local_storage,
    )
