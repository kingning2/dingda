# api

给 React / Tauri WebView 的 HTTP。这里**只做路由**：校验入参、调 `domains` / `mcp.catalog`，不写闲鱼签名、不开浏览器。

`router.py` 把下面这些 router 挂到 `app.py` 上。前缀以各文件里的 `APIRouter(prefix=...)` 为准。

## 本目录文件

### `router.py`

唯一聚合点。按顺序 `include_router`：health → bootstrap → runtime → channel → account → agent → crawler → mcp → research。新增 HTTP 模块必须在这里挂上，否则 `create_app` 看不到。

### `health.py`

`GET /health`。给 Rust 壳探活：`{"status":"ok","phase": current_phase()}`。**不**跑完整预热。

### `bootstrap.py`

`GET /v1/bootstrap`。立刻返回壳首屏快照（runtime + warmup phase），并用 `BackgroundTasks` 调 `ensure_warmed()` 做完整预热（含闲鱼 token 探活调度）。

### `runtime.py`

`GET /v1/runtime/status`。`RuntimeService().snapshot()`：Python 进程是否就绪。不是 Codex/Claude 的 runtime。

### `channel.py`

扫码 HTTP：

- `POST /v1/channel/qr/start` — 选平台，启动后台扫码，返回 task id
- `GET /v1/channel/qr/check` — 轮询 `LoginSnapshot`（二维码、已扫、成功 cookie）

实现在 [../domains/channel/README.md](../domains/channel/README.md)，平台页在 [../channels/README.md](../channels/README.md)。

### `account.py`

账号 HTTP（`/v1/accounts`）：

- `GET ""` — 列表，可按 `platform` 过滤
- `GET /{account_id}/profile` — 个人主页摘要（扫码时已存的名称头像）
- `PATCH /{account_id}` — 改展示名、自动连接等偏好
- `POST /{account_id}/connect` / `disconnect`
- `DELETE /{account_id}`

登录态写入来自扫码成功路径，不在这些 handler 里塞 cookie。服务见 [../domains/account/README.md](../domains/account/README.md)。

### `agent.py`

`/v1/agent`：

- `GET /preferences` — 读默认 Agent + 各 Agent 默认模型映射
- `GET /default` — 读 SQLite 里当前默认外部 Agent id
- `PUT /default` — 写入默认 Agent id（body: `{ "agent_id": "..." }`）
- `PUT /default-model` — 写入某 Agent 默认模型（body: `{ "agent_id", "model_id" }`）
- `GET /works/{work_id}` — 读 AI 工作对话快照
- `PUT /works/{work_id}` — 覆盖写入对话快照（body: `{ "detail": { ... } }`）

CLI PATH 探测仍在 Tauri；产品 Agent SSE 起来后也挂这里，实现走 [../agent/README.md](../agent/README.md) + [../tools/README.md](../tools/README.md)。

### `crawler.py`

`/v1/crawler` 前缀，**目前是空骨架**。产品页爬虫任务应调 [../crawler/README.md](../crawler/README.md)，不要从这里 import Playwright。

### `mcp.py`

`GET /v1/mcp/servers`。返回内置 MCP 配置列表，给设置页/壳注入 Codex。内容来自 `mcp.catalog.list_builtin_mcp_servers()`，不是 MCP stdio 本身。stdio 见 [../mcp/README.md](../mcp/README.md)。

### `research.py`

`/v1/research` 前缀，**目前是空骨架**。调研 workflow 在 [../agent/workflows/README.md](../agent/workflows/README.md)。

## 子目录

无。DTO 在 [../contracts/README.md](../contracts/README.md)。
