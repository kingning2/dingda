# crawler/core

所有 Source 共用的插座和结果类型。**不要**在这里写闲鱼卡片 CSS、mtop API 名。

## 本目录文件

### `base.py`

- `BrowserSessionOptions` — 代理、指纹、cookies、`cookie_domain`（dict cookie 注入时必填，如 `.goofish.com`）
- `BrowserCrawler` — 打开/关闭带 ContextOptions 的 Page；子类实现 `search`；`detail`（单条详情）与
  `browse`（连贯浏览：一个 page 内列表 → 逐个点开详情，直播是连续画面）默认未实现，支持的 Source 覆盖
- `ApiCrawler` — 无浏览器插座（官方 HTTP 找货等）；子类实现 `search`

开页策略只写一遍：Source 不要自己 `launch` 浏览器。API 平台走 `ApiCrawler`，不 acquire BrowserPort。

### `live.py`

爬取过程直播帧。受 `ctx.meta["live_frame_enabled"]` 开关控制，截图经 `BrowserPort.screenshot`
推给 `ctx.meta["on_live_frame"]` 回调（无回调则不推）。全程不碰 Playwright。

### `pacing.py`

平台读操作的**进程级**最小间隔闸门。`pace(key, min_interval=…)` 只等不抛：并发调用各自领一个
往后排的号（读改写 `_next_at` 之间没有 `await`，所以不必上锁），间隔多少由调用方决定。
闲鱼详情用它避免连拉太快被限流 —— 与 `channels/xianyu/limiter.py` 的写令牌桶不同，
那个超限即拒，这个只是排队。

### `types.py`

- `CrawlContext` — `task_id`、可选 `account_id`、`meta`（直播开关、平台参数都走这里）
- `CrawlItem` — 标准化商品（id、标题、价、链接、raw）
- `CrawlResult` — items + 可选 raw_html

Agent 节点把 `CrawlItem` 映射成商品/笔记出参。

### `__init__.py`

包标记。

## 子目录

无。闲鱼实现：[../sources/xianyu/README.md](../sources/xianyu/README.md)。
