"""渠道工厂（对标 CowAgent channel_factory.create_channel）。"""



from __future__ import annotations



from src.channels.base import QrLoginChannel

from src.channels.xianyu.channel import XianyuQrChannel

from src.channels.xiaohongshu.channel import XiaohongshuQrChannel

from src.shared.errors import AppError



_CHANNELS: dict[str, type[QrLoginChannel]] = {

    "xianyu": XianyuQrChannel,

    "xiaohongshu": XiaohongshuQrChannel,

}





def create_qr_login_channel(platform: str) -> QrLoginChannel:

    channel_cls = _CHANNELS.get(platform)

    if channel_cls is None:

        raise AppError("channel.qr_unsupported", f"不支持的平台：{platform}")

    return channel_cls()

