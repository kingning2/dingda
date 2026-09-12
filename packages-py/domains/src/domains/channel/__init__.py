"""Channel 领域包导出。"""

from domains.channel.qr_service import ChannelQrService, get_channel_qr_service
from domains.channel.service import ChannelService

__all__ = [
    "ChannelQrService",
    "ChannelService",
    "get_channel_qr_service",
]
