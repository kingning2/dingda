# domains/channel

两块：**正在用的扫码任务**，和 **尚未接线的 IM 长连编排骨架**。不要混。

## 本目录文件

### `qr_service.py`

内存扫码会话（TTL 300s）：

- `start`：`create_qr_login_channel(platform)`，生成 session_id，后台 Channel 出码
- `check`：把 `LoginSnapshot` 变成 `QrCheckResponse`；成功则 `save_login_credentials`

`api/channel.py` 只调这里。平台超时：闲鱼 120s，小红书 240s。

### `service.py`

`ChannelService`：**骨架**（旧 sidecar WSS/自动回复设想）。产品 IM 目前走 Tool `chats`/`send` + `channels.xianyu.ws`，不经过本类。

### `__init__.py`

包标记。

## 子目录

无。平台 Channel：[../../channels/README.md](../../channels/README.md)。
