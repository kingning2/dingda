"""多渠道对接层（登录、消息 — Phase A 先落地扫码登录）。"""

from src.channels.registry import create_qr_login_channel
from src.channels.types import LoginSnapshot, LoginStatus

__all__ = ["LoginSnapshot", "LoginStatus", "create_qr_login_channel"]
