# cli/live

CLI 运行期间的直播帧总线（跨进程 → SSE）。

## 本目录文件

- `hub.py` — 按 run_id 登记队列；`preview` 工具经
  [../../tools/live_push.py](../../../../tools/src/tools/live_push.py) 投帧，spawn 侧 `drain` 进 SSE。
  队列有界，满了丢最旧帧，避免阻塞浏览器推帧。

## 子目录

无。
