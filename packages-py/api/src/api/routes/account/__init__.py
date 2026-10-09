"""账号路由域。

职责：
    聚合 account 域各端点挂到 ``/v1/accounts``；每端点一个文件。
    登录态由扫码 / 探活侧写入，本域只做读、删与偏好 PATCH。
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.account import (
    browser_session,
    connect_account,
    delete_account,
    disconnect_account,
    list_accounts,
    patch_account,
    profile,
)

router = APIRouter(tags=["accounts"])
router.include_router(list_accounts.router)
router.include_router(browser_session.router)
router.include_router(profile.router)
router.include_router(patch_account.router)
router.include_router(connect_account.router)
router.include_router(disconnect_account.router)
router.include_router(delete_account.router)
