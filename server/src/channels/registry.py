"""渠道工厂（对标 CowAgent channel_factory.create_channel）。

职责：
    按 platform 名取出扫码 Channel 插头。
"""

from __future__ import annotations

from src.channels.ali1688.channel import Ali1688QrChannel
from src.channels.base import QrLoginChannel
from src.channels.xianyu.channel import XianyuQrChannel
from src.channels.xiaohongshu.channel import XiaohongshuQrChannel
from src.shared.errors import AppError

_CHANNELS: dict[str, type[QrLoginChannel]] = {
    "xianyu": XianyuQrChannel,
    "xiaohongshu": XiaohongshuQrChannel,
    "ali1688": Ali1688QrChannel,
}


def create_qr_login_channel(platform: str) -> QrLoginChannel:
    """按平台名创建扫码 Channel。"""
    channel_cls = _CHANNELS.get(platform)
    if channel_cls is None:
        raise AppError("channel.qr_unsupported", f"不支持的平台：{platform}")
    return channel_cls()
