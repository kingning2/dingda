# core

进程级底座：配置、日志、错误类型、上下文压缩。不含闲鱼/账号规则，也不含 FastAPI 装配。

## 本目录文件

### `config.py`

`Settings`：`host`/`port`/`log_level`/`reload`。来源：`__main__` 参数 + `DINGDA_*` 环境变量 + 默认 `127.0.0.1:8787`。

### `logging.py`

`configure_logging`、`uvicorn_log_config`、带 context 的 `info/warning/error`。业务模块用 `logging.getLogger("dingda....")`，不要另起一套 print。

### `errors.py`

`AppError` 及派生：可在 domain / api 层抛出，由 FastAPI 异常处理器映射为稳定 HTTP 状态码与错误 JSON（`{ok:false, code, message}`）。

### `compress.py`

Headroom 上下文压缩的统一入口：`compress_messages` / `compress_text` / `compress_tool_payload`。惰性导入 `headroom`，是否启用由 `DINGDA_HEADROOM` 决定（默认开）；不可用时透传原文。

### `__init__.py`

包标记。

## 子目录

无。FastAPI 生命周期与预热在 `packages-py/api/src/api/boot/`（`lifespan.py` / `warmup.py`），应用工厂在 `packages-py/api/src/api/app.py`。
