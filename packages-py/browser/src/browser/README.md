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

**等待原语**——超时一律返回 `False`/`None`、**不抛**。风控页永远等不到正常元素，抛异常会把
「被拦」误报成「抽取失败」：

- `wait_for_selector(selector, state=…)` / `wait_for_load_state(state=…)`
- `wait_for_function(expression, arg)`：固定 200ms 轮询。引擎默认按帧跑，而判据常要读
  `innerText`（触发 layout），按帧等于占满主线程、反而拖慢页面渲染。
- `wait_for_response(url_contains)`：用**子串**谓词而非 Playwright 的 URL 参数（后者是 glob，
  `/api/login` 会被当整串模式）。

**事件 hook**——`PageEvent` 用平台无关命名（`NAVIGATION_START` / `DOM_READY` / `LOADED` /
`REQUEST` / `RESPONSE` / `REQUEST_DONE` / `REQUEST_FAILED` / `PAGE_ERROR` / `CLOSED`）：

- `on(event, handler) -> 取消函数`。导航类事件**必须在 `goto` 之前注册**，否则错过。
- `wait_for_event(event, url_contains=…)`：监听从调用时才开始，**不补发**已发生的事件。
- 负载统一归一化成 `PageEventInfo`（url/method/status/resource_type/error/message），
  不漏引擎对象；handler 抛异常只记日志，不打断页面派发。

**事件日志**——构造时自动给 9 个事件挂统一日志，与「有没有人订阅」解耦，排查时不必先改代码加订阅。
级别按事件分：生命周期 INFO、`request_failed` / `page_error` WARNING、高频网络事件 DEBUG
（一次搜索几百个请求，INFO 下会刷屏）。URL 与文本超 200 字符截断并标注原始长度。
**排查页面问题时开 DEBUG，grep `页面事件` 即得完整时间线。**

**平台无关纪律**：本层只给生命周期与网络事件，站点差异（选择器 / URL 片段 / JS 判据）一律留在
平台层；日志文案里不出现任何站点名。

回归探针：`python -m api.scripts.probe_page_waits`（本地 HTTP 页 + 真实 Camoufox，不碰平台、
不触发风控，验证「传 `(arg) => …` 时是否真在等」以及日志与事件捕获）。

### `context.py`

`ContextOptions`；`normalize_cookies` / `cookies_to_playwright` / `serialize_cookies` / `proxy_server`。域名由调用方填进 `Cookie.domain`，本文件不写 `.goofish.com`。

### `sync.py`

扫码专用线程上的同步 Camoufox；同样走 `camoufox_bin.require_camoufox_exe()`。

### `camoufox_bin.py`

解析 `DINGDA_CAMOUFOX_EXE` / 本地解压缓存；不联网下载。

### `sync.py`

`sync_headless_page(...)`：必须在专用线程 `dingda-sync-browser` 里调用。探活用 `run_on_sync_browser`，扫码长任务用 `submit_on_sync_browser`。复用同一 Camoufox，每次独立 Context；任务结束关页不关进程。

### `__init__.py`

包标记。

## 子目录

- [adapters/](adapters/README.md) — 浏览器实现（Camoufox）

闲鱼自动过滑块不在本目录，见 [../channels/xianyu/slider.py](../../../channels/src/channels/xianyu/README.md)。