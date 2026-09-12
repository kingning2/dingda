# infrastructure/events

单进程内存总线。不跨进程、不落盘。Agent 步骤、扫码进度以后可 `publish("topic", payload)` 给 SSE。

## 本目录文件

### `bus.py`

`EventBus.subscribe(handler)` / `publish(topic, payload)`。handler 签名 `(topic, dict)`。当前产品路径尚未全挂上；模块头有使用示例。

### `__init__.py`

包标记。

## 子目录

无。
