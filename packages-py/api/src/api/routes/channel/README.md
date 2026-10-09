# channel/

`/v1/channel`：扫码登录 HTTP。

- `qr_start.py` — `POST /qr/start` 选平台，启动后台扫码，返回 task id
- `qr_check.py` — `GET /qr/check` 轮询 `LoginSnapshot`（二维码、已扫、成功 cookie）
- `qr_cancel.py` — `POST /qr/cancel` 关闭弹窗时打断后台浏览器任务

实现在 [channel 域](../../../../../domains/src/domains/channel/README.md)，
平台页在 [channels 包](../../../../../channels/src/channels/README.md)。
