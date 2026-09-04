"""渠道通用类型（登录状态机与快照）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

# API 契约用字符串；内部用 LoginStatus 枚举。
LoginStatusName = Literal["waiting", "scanned", "success", "failed", "expired"]


class LoginStatus(StrEnum):
    WAITING = "waiting"
    SCANNED = "scanned"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"


class QrCancelled(Exception):
    """关掉扫码弹窗或重新发起扫码，后台任务应立刻让出浏览器。"""


@dataclass(frozen=True)
class LoginSnapshot:
    status: LoginStatus
    qr_base64: str | None = None
    qr_url: str | None = None
    detail: str | None = None
    account_id: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    cookie: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status.value,
            "qr_base64": self.qr_base64,
            "qr_url": self.qr_url,
            "detail": self.detail,
            "account_id": self.account_id,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "cookie": self.cookie,
        }
