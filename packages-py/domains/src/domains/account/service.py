"""账号领域服务（SQLite 编排）。"""

from __future__ import annotations

import logging

from contracts.account import (
    AccountDeleteResponse,
    AccountListResponse,
    AccountPatchRequest,
    AccountProfileResponse,
    AccountProfileView,
    AccountRecord,
    AccountUpsertResponse,
)
from domains.account.session import build_session_views
from infrastructure.db import accounts as account_repo
from core.errors import AppError

logger = logging.getLogger("dingda.account.service")


def probe_ali1688_account(stored_raw: str) -> bool | None:
    """账户上存的这把 1688 AK 现在还作数吗。三态：好 / 明确被拒 / 没问到。

    两段分工不同。本地那段（``ak.probe``）是纯字符串比对，管的是「AK 文件被删了 /
    换成了另一把」这种不问就知道的事，为它跑一趟网络是浪费。本地对得上才打网关 ——
    因为**本地对得上不等于凭据还能用**：AK 被网关吊销或过期时，文件还在、
    字符串也还是那一串，只有真打一次才知道。

    ``None`` 表示没问到（网络不通 / 限流 / 网关 5xx）。调用方**不许把它当成失效**：
    前端拿到 ``auth_valid=False`` 会弹「登录已过期，请重新扫码」，拿一次网络抖动换
    用户白扫一次码，比多显示一会儿「已登录」更糟。

    读写账户的两个入口（``_sync_ali1688_auth`` 与 ``token_scheduler``）共用这一份判断，
    免得两边各写一遍、各自漂移。
    """
    from channels.ali1688.ak import probe as probe_ali1688_ak
    from channels.ali1688.client import probe_credentials

    if not probe_ali1688_ak(stored_raw):
        return False
    return probe_credentials()


def _to_record(row: account_repo.AccountRow) -> AccountRecord:
    session, actions = build_session_views(
        row.platform,  # type: ignore[arg-type]
        auth_valid=row.auth_valid,
        connected=row.connected,
    )
    return AccountRecord(
        account_id=row.account_id,
        platform=row.platform,  # type: ignore[arg-type]
        display_name=row.display_name,
        avatar_url=row.avatar_url,
        cookie=row.cookie,
        status=row.status,
        has_cookie=bool(row.cookie.strip()),
        auto_connect=row.auto_connect,
        auth_valid=row.auth_valid,
        session=session,
        actions=actions,
    )


class AccountService:
    def list(self, *, platform: str | None = None) -> AccountListResponse:
        if platform in (None, "ali1688"):
            self._sync_ali1688_auth()
        rows = account_repo.list_accounts(platform=platform)
        return AccountListResponse(items=[_to_record(row) for row in rows])

    def patch(self, account_id: str, request: AccountPatchRequest) -> AccountUpsertResponse:
        existing = account_repo.get_account(account_id.strip())
        if not existing:
            raise AppError("account.not_found", "账号不存在", status_code=404)

        display_name = request.display_name.strip() if request.display_name else existing.display_name
        auto_connect = (
            request.auto_connect
            if request.auto_connect is not None
            else existing.auto_connect
        )
        row = account_repo.upsert_account(
            account_id=existing.account_id,
            platform=existing.platform,
            display_name=display_name,
            cookie=existing.cookie,
            status=existing.status,
            auto_connect=auto_connect,
        )
        return AccountUpsertResponse(item=_to_record(row))

    def connect(self, account_id: str) -> AccountUpsertResponse:
        existing = account_repo.get_account(account_id.strip())
        if not existing:
            raise AppError("account.not_found", "账号不存在", status_code=404)
            
        if not existing.cookie.strip():
            raise AppError("account.no_cookie", "账号缺少登录信息", status_code=400)

        account_repo.set_connected(existing.account_id, True)
        logger.info("闲鱼账号已连接: %s", existing.account_id)
        row = account_repo.get_account(existing.account_id)
        if not row:
            raise AppError("account.not_found", "账号不存在", status_code=404)
        return AccountUpsertResponse(item=_to_record(row))

    def disconnect(self, account_id: str) -> AccountUpsertResponse:
        existing = account_repo.get_account(account_id.strip())
        if not existing:
            raise AppError("account.not_found", "账号不存在", status_code=404)

        account_repo.set_connected(existing.account_id, False)
        logger.info("闲鱼账号已断开: %s", existing.account_id)
        row = account_repo.get_account(existing.account_id)
        if not row:
            raise AppError("account.not_found", "账号不存在", status_code=404)
        return AccountUpsertResponse(item=_to_record(row))

    def delete(self, account_id: str) -> AccountDeleteResponse:
        if not account_id.strip():
            raise AppError("account.invalid_id", "账号 ID 不能为空", status_code=400)
        existing = account_repo.get_account(account_id.strip())
        if not existing:
            raise AppError("account.not_found", "账号不存在", status_code=404)
        deleted = account_repo.delete_account(existing.account_id)
        if not deleted:
            raise AppError("account.not_found", "账号不存在", status_code=404)
        if existing.platform == "ali1688":
            from channels.ali1688.ak import clear_account_ak

            clear_account_ak(existing.cookie)
            logger.info("1688 账号已删除并清除 AK: %s", existing.account_id)
        return AccountDeleteResponse(deleted=True)

    def profile_page(self, account_id: str) -> AccountProfileResponse:
        """打开账号卡片：用扫码时已存的名称头像。"""
        existing = account_repo.get_account(account_id.strip())
        if not existing:
            raise AppError("account.not_found", "账号不存在", status_code=404)

        return AccountProfileResponse(
            profile=AccountProfileView(
                account_id=existing.account_id,
                platform=existing.platform,  # type: ignore[arg-type]
                display_name=existing.display_name,
                avatar_url=existing.avatar_url,
            )
        )

    def _sync_ali1688_auth(self) -> None:
        """列表前探活：账户存的 AK 现在还作不作数（见 ``probe_ali1688_account``）。

        判据只认确定的两种：``None``（网络抖动 / 限流 / 网关抽风）**不写库**。
        """
        for row in account_repo.list_accounts(platform="ali1688"):
            valid = probe_ali1688_account(row.cookie)
            if valid is None:
                logger.info("1688 探活没问到答案，保持原状态 account=%s", row.account_id)
                continue
            if valid != row.auth_valid:
                account_repo.set_auth_valid(row.account_id, valid)


_service = AccountService()


def get_account_service() -> AccountService:
    return _service
