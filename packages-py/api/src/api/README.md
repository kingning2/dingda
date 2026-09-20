# api

给 React / Tauri WebView 的 HTTP。这里**只做路由**：校验入参、调 `domains`，不写闲鱼签名、不开浏览器。

`router.py` 把下面这些 router 挂到 `app.py` 上。前缀以各文件里的 `APIRouter(prefix=...)` 为准。

## 本目录文件

### `router.py`

唯一聚合点。按顺序 `include_router`：health → bootstrap → runtime → channel → account → agent → llm → research → watch。新增 HTTP 模块必须在这里挂上，否则 `create_app` 看不到。

### `health.py`

`GET /health`。给 Rust 壳探活：`{"status":"ok","phase": current_phase()}`。**不**跑完整预热。

### `bootstrap.py`

`GET /v1/bootstrap`。立刻返回壳首屏快照（runtime + warmup phase），并用 `BackgroundTasks` 调 `ensure_warmed()` 做完整预热（`init_db` 之后挂闲鱼 token 探活调度）。

### `runtime.py`

`GET /v1/runtime/status`。`RuntimeService().snapshot()`：Python 进程是否就绪。指的是 Python 侧运行时，不是任何外部 CLI。

### `channel.py`

扫码 HTTP：

- `POST /v1/channel/qr/start` — 选平台，启动后台扫码，返回 task id
- `GET /v1/channel/qr/check` — 轮询 `LoginSnapshot`（二维码、已扫、成功 cookie）
- `POST /v1/channel/qr/cancel` — 取消一次进行中的扫码

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

- `GET /works` — 最近工作列表（按 `updated_at` 倒序）
- `GET /works/{work_id}` — 读 AI 工作对话快照
- `PUT /works/{work_id}` — 覆盖写入对话快照（body: `{ "detail": { ... } }`）
- `POST /works/{work_id}/run` — 跑一轮 Agent（SSE）
- `POST /runtimes/{runtime_id}/run` — 同上的兼容路径（`runtime_id` 只进日志与 `runStarted`）
- `GET /runtimes/runs/{run_id}/events?after=<seq>` — **接回**一次运行：先重放 `seq > after`
  的已投递事件，再续上直播直到跑完。run 已被回收时 404
- `POST /runtimes/runs/{run_id}/cancel` — 取消一次运行（只能停在步与步之间）
- `GET /works/{work_id}/active-run` — 进页面时的活跃探针：这个 work 下有没有在跑的 run。
  顺带 `manager.reap()` —— 这条是唯一保证会被打开的入口

本文件**只管路由**：校验 `prompt`、把 `stream_run` / `resume_run` 包成 `StreamingResponse`。
执行接线在 [agent_run.py](agent_run.py)；`AgentRunRequest` 也定义在那里（放本文件会让
`agent_run` 反过来 import 本模块，绕成环）。请求体只剩 `prompt` / `run_id` / `work_id` /
`model_id` / `platform_hint` / `context_messages`；`work_id` 是断线后找回在跑 run 的键
（`/runtimes/...` 这条路径里没有 work 信息，所以只能走 body）。

事件契约见 [../contracts/README.md](../../../contracts/src/contracts/README.md)。

### `agent_run.py`

**Agent 运行接线**：建模型客户端、装配 `RunContext`，把运行交给 `agent.runs`。

**run 的寿命不等于这个 HTTP 请求的寿命。** 这里没有 `_RUNNING` —— 生命周期、投递日志、
取消、在跑查询全归 `agent.runs.RunManager`（进程内单例 `manager`）。`stream_run` 只是
「起手或接回一条 record，然后订阅它」：

```python
record = manager.get(run_id) or manager.start(run_id, ..., factory=_factory_for(...),
                                              seed_events=(runStarted,))
async for seq, event in manager.attach(run_id, after=0):
    yield record.bus.encode(event, seq=seq)
```

- `_factory_for` 把 cookie / auth / login / **llm 客户端**闭包进 `factory(bus, cancel)`。
  模型客户端在这里建、在这里 `aclose()`：它的寿命跟着 run 走，不再跟着请求走。
- 生成器被断开（用户关页面 / 刷新 / 断网）时只**退订**，不再取消任务、不再关连接。
  这条是「关掉应用后任务还在跑、重进能接回来」的前提。
- 「没有可用模型凭据」是**运行失败**而不是请求失败：`factory` 自己吃掉 `AppError`，
  往流里发一条 `error` 再收尾，前端能看见人话。
- `resume_run` 同一套实现，只多一个 `after` 起点。

编排顺序仍在 `agent.run.run_chat`：`runStarted` → 并发校验三平台登录态（失效平台
`textDelta` + 二维码 `browserFrame`）→ 主编排 → 必要时修复子 agent。`runCompleted`
由 `agent.runs._drive` 保证在日志末尾补上 —— 前端靠它把界面从「运行中」放下来。

SSE 帧由 [sse.py](sse.py) 的 `EventBus.encode(event, seq=...)` 编：`seq` 落进 `id:` 行，
既是重放游标，也是将来 AG-UI `Last-Event-ID` 的载体。总线本身的推送口没变
（`bus.text(...).after(coro)`：「先推『请扫码』，再阻塞等扫码」）。

### `watch.py`

`/v1/watch`：商品监控——把一批商品长期盯着，看卖不卖得掉、降没降价。

- `POST /targets` — 批量加入监控（同 `platform+item_id` 幂等）
- `GET /targets` — 列表，带涨跌额与售出态
- `GET /targets/{target_id}` — 单条：完整价格历史点 + 变更事件
- `PATCH /targets/{target_id}` — 改状态（active/paused/archived）或轮询间隔
- `DELETE /targets/{target_id}` — 彻底移除（含历史）；想留历史改用 PATCH 归档
- `GET /summary` — 概览：多少还在卖、多少卖掉了、多少降价了

⚠️ **后台轮询当前没插上**：原 `watch_feed.py`（用旧 `tools.product` 实现
`domains.watch.base.ProductFetcher`）已随 `packages-py/tools` 删除，所以
`boot/warmup.py` 现在只挂闲鱼 token 探活调度。加进监控的目标会落库、能在页面上看到，
但**不会自动轮询**。重接时在 `api` 用 `agent/nodes` 详情节点实现 `ProductFetcher`。
业务见 [../domains/watch/README.md](../../../domains/src/domains/watch/README.md)。

### `llm.py`

`/v1/llm`：模型凭据——用哪个供应商、哪把 key、哪个模型。**多条并存，一条生效**。

- `GET /providers` — 供应商目录（前端下拉数据源；`requires_model` 由「有没有默认模型」推出）
- `POST /models` — 按一组**还没保存**的连接参数拉可用模型（表单里刚粘上 key 就能拉）
- `GET /credentials` — 全部凭据 + 当前使用中的 id（key 只回掩码）
- `GET /credentials/{id}/models` — 用已保存凭据的 key 拉可用模型（编辑态只能走这条）
- `POST /credentials` — 新建（`activate` 默认 true）
- `PUT /credentials/{id}` — 改；请求里没出现的字段就是不改，`base_url: null` 表示恢复供应商默认
- `DELETE /credentials/{id}`
- `POST /credentials/{id}/activate` — 设为唯一使用中
- `POST /credentials/{id}/test` — 发一次最小请求验连通性，结果记到该条凭据上
- `POST /credentials/import-env` — 把 `.env` / 真实环境里那份配置收编成一条凭据（查重）

四处口径：

- **供应商目录在这一层转换并注入领域服务**。目录的真相在 `agent.llm.providers`，而
  `domains` 不许 import `agent`；`api` 是唯一同时认识两边的地方
- **组装 `LlmClient` 需要 key 原文，而 key 不进任何契约**，所以检测端点与模型列表端点
  都直接读 `infrastructure.db.llm_credentials`，不经领域服务。领域服务管的是凭据生命周期，
  不是客户端构造
- **检测失败与拉模型列表失败都回 200 + `ok=false`**，并带上 `agent` 的 `llm.*` 精确错误码
  （`llm.auth_failed` / `llm.model_required` / `llm.timeout` …）。填错豆包接入点 ID
  时用户该看到「模型或路径不存在」，不是一句「请求失败」
- **模型列表为空不算失败**：有的网关就是不给列表（方舟只认 `ep-` 接入点），
  这时回 `ok=true` + `models: []` + `EMPTY_MODELS_HINT`，前端据此保留手填入口。
  失败分支也带上 `default_model`，否则「`provider=deepseek` 却 `default_model=null`」
  与 `/providers` 的说法自相矛盾

**发动机消费这份凭据的方式见 [agent_run.py](agent_run.py)**：取「使用中」那条，把
`api_key` / `model` / `base_url` **显式**传给 `resolve_settings`（显式入参优先级最高，
见 [agent/llm/README.md](../../../agent/src/agent/llm/README.md)）。读库留在本层，
不下沉进 `agent` —— 那会反过来依赖 `infrastructure`。

业务见 [../domains/llm/README.md](../../../domains/src/domains/llm/README.md)。

### `research.py`

`/v1/research` 前缀，**目前是空骨架**，还没有挂任何路由。

## 子目录

- [boot/](boot/warmup.py) — 渐进式预热：先响应壳层探活，再后台 `init_db` 并挂闲鱼 token 探活调度

DTO 在 [../contracts/README.md](../../../contracts/src/contracts/README.md)。
