# api

给 React / Tauri WebView 的 HTTP。这里**只做路由**：校验入参、调 `domains`，不写闲鱼签名、不开浏览器。

`router.py` 把下面这些 router 挂到 `app.py` 上。前缀以各文件里的 `APIRouter(prefix=...)` 为准。

## 本目录文件

### `router.py`

唯一聚合点。按顺序 `include_router`：health → bootstrap → runtime → channel → account → agent → crawler → research → watch。新增 HTTP 模块必须在这里挂上，否则 `create_app` 看不到。

### `health.py`

`GET /health`。给 Rust 壳探活：`{"status":"ok","phase": current_phase()}`。**不**跑完整预热。

### `bootstrap.py`

`GET /v1/bootstrap`。立刻返回壳首屏快照（runtime + warmup phase），并用 `BackgroundTasks` 调 `ensure_warmed()` 做完整预热（含闲鱼 token 探活调度与商品监控轮询调度）。

### `runtime.py`

`GET /v1/runtime/status`。`RuntimeService().snapshot()`：Python 进程是否就绪。不是 Codex/Claude 的 runtime。

### `channel.py`

扫码 HTTP：

- `POST /v1/channel/qr/start` — 选平台，启动后台扫码，返回 task id
- `GET /v1/channel/qr/check` — 轮询 `LoginSnapshot`（二维码、已扫、成功 cookie）

实现在 [../domains/channel/README.md](../../../domains/src/domains/channel/README.md)，平台页在 [../channels/README.md](../../../channels/src/channels/README.md)。

### `account.py`

账号 HTTP（`/v1/accounts`）：

- `GET ""` — 列表，可按 `platform` 过滤
- `GET /{account_id}/profile` — 个人主页摘要（扫码时已存的名称头像）
- `PATCH /{account_id}` — 改展示名、自动连接等偏好
- `POST /{account_id}/connect` / `disconnect`
- `DELETE /{account_id}`

登录态写入来自扫码成功路径，不在这些 handler 里塞 cookie。服务见 [../domains/account/README.md](../../../domains/src/domains/account/README.md)。

### `agent.py`

`/v1/agent`：

- `GET /preferences` — 读默认 Agent + 各 Agent 默认模型映射
- `GET /default` — 读 SQLite 里当前默认外部 Agent id
- `PUT /default` — 写入默认 Agent id（body: `{ "agent_id": "..." }`）
- `PUT /default-model` — 写入某 Agent 默认模型（body: `{ "agent_id", "model_id" }`）
- `GET /works/{work_id}` — 读 AI 工作对话快照
- `PUT /works/{work_id}` — 覆盖写入对话快照（body: `{ "detail": { ... } }`）
- `POST /works/{work_id}/run` — 产品 Agent SSE（进程内 Tool + Headroom）
- `POST /runtimes/{runtime_id}/run` — 外部 CLI SSE（Python spawn；codex / claude / opencode）
- `POST /runtimes/runs/{run_id}/live-frame` — `preview` 工具投递浏览器直播帧
- `POST /runtimes/runs/{run_id}/cancel` — 取消 CLI 运行

CLI PATH 探测 / 下载仍在 Tauri；启动与流式事件在本模块。实现见 [../agent/README.md](../../../agent/src/agent/README.md)。

### `crawler.py`

`/v1/crawler`：手动搜品与单品详情。

- `POST /search` — 一次性搜品，返回列表 + 搜索页 URL
- `POST /search/live` — SSE：`frame` / `result` / `error` / `done`
- `POST /product` — 单品详情（闲鱼：价格、想要人数、留言、`sold_state`）
- `POST /product/live` — SSE 同上

实现在 [../tools/README.md](../../../tools/src/tools/README.md) 与 [../crawler/README.md](../../../crawler/src/crawler/README.md)，不要从这里 import Playwright。

### `watch.py`

`/v1/watch`：商品监控——把一批商品长期盯着，看卖不卖得掉、降没降价。

- `POST /targets` — 批量加入监控（同 `platform+item_id` 幂等）
- `GET /targets` — 列表，带涨跌额与售出态
- `GET /targets/{target_id}` — 单条：完整价格历史点 + 变更事件
- `PATCH /targets/{target_id}` — 改状态（active/paused/archived）或轮询间隔
- `DELETE /targets/{target_id}` — 彻底移除（含历史）；想留历史改用 PATCH 归档
- `GET /summary` — 概览：多少还在卖、多少卖掉了、多少降价了
- `POST /poll` — 立刻轮询几条（手动验证用，最多 5 条）

后台定时轮询由 [boot/warmup.py](boot/warmup.py) 在 `init_db` 之后挂 `domains.watch.scheduler`，不在本层。业务见 [../domains/watch/README.md](../../../domains/src/domains/watch/README.md)。

### `watch_feed.py`

商品监控**取数插头**：用 `tools.product` 实现 `domains.watch.base.ProductFetcher` 插座。

`domains` 不依赖 `tools`，而本层是唯一同时依赖两者的地方，所以插头放这里。
必须传 `allow_login_recovery=False`——后台轮询不能弹扫码窗，会话过期就让这次轮询失败、
由 token 调度器去静默续期。

### `research.py`

`/v1/research` 前缀，**目前是空骨架**。调研 workflow 在 [../agent/workflows/README.md](../../../agent/src/agent/workflows/README.md)。

## 子目录

- [boot/](boot/warmup.py) — 渐进式预热：先响应壳层探活，再后台加载 DB 与挂调度器

DTO 在 [../contracts/README.md](../../../contracts/src/contracts/README.md)。
