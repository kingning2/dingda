# browser

通用浏览器能力。Crawler / Channel 只依赖 `BrowserPort` 和 `Cookie`。  
禁止出现闲鱼、1688、商品、价格、mtop。

默认引擎名 `camoufox`（registry）。扫码线程用同步 `sync_headless_page`，采集用 async Manager + Pool。

## 本目录文件

### `port.py`

插座：`Cookie`、`LaunchOptions`、抽象 `Page`（goto/click/fill/evaluate/screenshot/cookies）、抽象 `BrowserPort`（start/stop/new_page）。改能力先改这里，再改 adapter。

### `registry.py`

`create_browser("camoufox")`。`list_engines()`。

### `instance.py`

`BrowserInstance`：一台独立 Camoufox 进程，带 `browser_id` 与状态 starting/ready/busy/idle/closing/stopped。可带独立 `user_data_dir` profile。

### `pool.py`

单机 `BrowserPool`：`max_browsers`（默认 3，`DINGDA_BROWSER_MAX`）、`max_contexts_per_browser`（默认 5，`DINGDA_BROWSER_MAX_CONTEXTS`）。空闲优先复用，未满则新建，满则等待。空闲超时（默认 10 分钟，`DINGDA_BROWSER_IDLE_SECONDS`）回收。启动失败重试；异常退出 `retire` 后按需再拉起。不引入 Redis/K8s。

### `manager.py`

`BrowserManager`：Pool 门面。采集 `get_browser_manager().acquire()` / `release(port)`。Crawler 不得 launch/close 引擎。风控恢复仍自建 Manager + `start`/`stop`（钉住一台，不进采集池）。

### `page.py`

`PlaywrightPage`：把 Camoufox 页包成 `port.Page`（底层是 Playwright 协议，不是第二种浏览器）。

### `context.py`

`ContextOptions`；`normalize_cookies` / `cookies_to_playwright` / `serialize_cookies` / `proxy_server`。域名由调用方填进 `Cookie.domain`，本文件不写 `.goofish.com`。

### `session.py`

`async with BrowserSession(port)`：拿一页，离开自动 close。Crawler 基类内部会用类似生命周期。

### `sync.py`

`sync_headless_page(...)`：必须在专用线程 `dingda-sync-browser` 里调用。探活用 `run_on_sync_browser`，扫码长任务用 `submit_on_sync_browser`。复用同一 Camoufox，每次独立 Context；任务结束关页不关进程。

### `__init__.py`

包标记。

## 子目录

- [adapters/](adapters/README.md) — 浏览器实现（Camoufox）

闲鱼自动过滑块不在本目录，见 [../channels/xianyu/slider.py](../channels/xianyu/README.md)。