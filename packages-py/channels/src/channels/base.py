"""扫码登录渠道抽象（对标 CowAgent Channel 生命周期）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from channels.types import LoginSnapshot


class QrLoginChannel(ABC):
    """各平台扫码登录的统一入口：start_login → 后台轮询 → snapshot。"""

    platform: ClassVar[str]

    @abstractmethod
    def start_login(self, *, timeout: int) -> Any:
        """启动后台登录任务，返回平台 runtime 句柄。"""

    @abstractmethod
    def snapshot(self, runtime: Any) -> LoginSnapshot:
        """读取当前登录快照（供 HTTP check 轮询）。"""
