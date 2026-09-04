# core

进程级：配置、日志、FastAPI 生命周期、预热、全局异常。不含闲鱼/账号规则。

## 本目录文件

### `config.py`

`Settings`：`host`/`port`/`log_level`/`reload`。来源：`__main__` 参数 + `DINGDA_*` 环境变量 + 默认 `127.0.0.1:8787`。

### `logging.py`

`configure_logging`、`uvicorn_log_config`、带 context 的 `info/warning/error`。业务模块用 `logging.getLogger("dingda....")`，不要另起一套 print。

### `lifespan.py`

`create_lifespan`：启动时 `init_db`，关闭时停共享 BrowserPool、同步扫码浏览器、`shutdown_db`。**不**在这里扫码。完整预热在 `warmup.py`。

### `exceptions.py`

`register_exception_handlers`：`AppError` → `{ok:false, code, message}`；校验失败 422；未捕获 500。

### `warmup.py`

壳先探活再后台热：phase `shell` → `warming` → `ready`。`ensure_warmed` 会 `init_db`、挂 `schedule_xianyu_token_scheduler`。`GET /health` 只读 `current_phase()`。

### `__init__.py`

包标记。

## 子目录

无。应用工厂：[../README.md](../README.md) 的 `app.py`。
