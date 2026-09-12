# 分层、依赖与 IPC（全 Skill 共享）

开发 Agent / Crawler / Browser / Tool 前先读本文件。这是桌面端 Web 产品 + Tauri 壳 + Python Runtime 的模块化约束，不是 DDD / 微服务教程。不要为完整性再加几十层抽象。

优先：职责清晰、依赖方向清晰、模块可替换、平台可扩展、测试容易。

---

## 核心规则（硬约束，原文必遵）

1. Browser = 浏览器能力层，只负责启动、Context、Page、导航、点击、输入、Cookie、Session、截图、网络监听等通用能力。
2. Crawler = 平台采集层，只负责闲鱼/1688等平台的搜索、详情、解析、标准化、Snapshot、Dedup。
3. Crawler 禁止直接依赖 Playwright / Camoufox，必须依赖 Browser Interface。
4. Browser 禁止出现 Xianyu、1688、商品、价格等平台业务逻辑。
5. 平台新增只修改 `crawler/sources/<platform>/`，浏览器新增只修改 `browser/adapters/<browser>/`。
6. 登录/账号语义属于 `channels/<platform>/`，Browser 只负责通用 Session/Cookie 能力。
7. Agent / MCP / Tool 不得直接操作 Playwright/Camoufox，统一通过 Tool → Crawler → Browser。
8. 禁止为了该架构新增 Rust Crawler、Rust Browser 或数据库层。

路径均在 `server/src/` 下（如 `server/src/crawler/sources/xianyu/`）。Python 目录树见 [`server/src/README.md`](../../server/src/README.md)；Tauri 壳见 [`packages-rs/client/src/README.md`](../../packages-rs/client/src/README.md)。上层 README 只引用下层。产品 SQLite 继续留在 Python `infrastructure/db`，不要为 Browser/Crawler 新开 Rust DB。

---

## 本仓库真实布局

前端是 **pnpm 工作区**（`packages/` + `apps/`），Rust 是 **Cargo 工作区**（`packages-rs/`）。
禁止沿用旧 OpenDesk 的路径（`packages/shared`、`packages/ui`、`apps/wework`、`src-tauri`）。

```text
apps/web/                Web 应用装配（Vite 根：index.html / 路由表 / 页面 / 启动编排）
packages/                前端 pnpm 工作区
  contracts/             与 Python 的线协议类型（纯类型，零运行时）
  client/
    routes/              路由契约（路径常量与解析）
    app-state/           跨域共享 UI 状态（Agent 运行时 / 账号 / 最近会话）
    runtime/             HTTP 传输 / 能力开关 / Server 状态 / 错误上报
    ui-theme/            设计令牌与全局样式
    ui-primitives/       无业务的原子组件 + cn()
    ui-layout/           窗口骨架：外壳 / 标题栏 / 导航栏
    ui-feedback/         错误边界与告警宿主
    ui-ai/               AI 消息渲染
    ui-composer/         输入区
    ui-account/          账号域
    ui-agent/            Agent 域
    ui-crawler/          采集域
    ui-home/             首页域
packages-rs/             Rust Cargo workspace（工作区根在仓库根 Cargo.toml）
  client/                Tauri 客户端（壳；唯一可执行体）
    src/commands/        壳 IPC（invoke）
  common/                日志出口 + 路径解析 + 平台标签
  camoufox/              Camoufox 定位与解压
  python/                Python 子进程起停与启动环境
  runtime/               CLI Runtime 定义 / 探测 / 托管下载
  agent/                 CLI Agent 目录与探测（IPC DTO）
server/src/             Python Server
  api/                   HTTP
  contracts/             Pydantic DTO
  channels/              登录 / cookie / 扫码（不是爬虫 Source）
  infrastructure/db/     产品 SQLite（Python 拥有）
  mcp/                   把能力暴露给外部 CLI（MCP stdio）
  domains/               现存应用服务（骨架 + 账号等）
```

包依赖单向无环：`common ← camoufox ← python ← client`、`common ← runtime ← agent ← client`。
成员包边界见 [`packages-rs/README.md`](../../packages-rs/README.md)。

---

## 两个「Agent」禁止混用

| 名称 | 路径 | 职责 |
|------|------|------|
| 产品 Agent | 目标：`server/src/agent/` | planning / tool 调用 / workflow |
| CLI Agent Runtime | 探测/下载：`packages-rs/runtime/src/` + `agent/`；**启动**：`server/src/cli/` | 壳负责 PATH/下载；Python 负责 spawn + SSE |

- 产品 Agent 的代码不要写进 `packages-rs/agent/src/` 或 `packages-rs/runtime/src/`。
- CLI **探测/下载**在 Tauri；**spawn/SSE**在 `server/src/cli/`，不要再写回 Tauri command。
- `server/src/domains/runtime/` 只是 Python 进程快照，不是垃圾桶，也不是 CLI Runtime。

---

## 调用关系（正确理解）

示意链（不是严格单向、也不是每层都要经过）：

```text
React
  ↓  HTTP/SSE/WSS（产品）或 Tauri invoke（壳）
Rust Application（壳）
  ↓  spawn
Python Runtime
  ↓
Agent
  ↓
Tool / Port
  ↓
Crawler
  ↓
Browser Adapter
  ↓
具体 Browser

Crawler
  ↓
Source Adapter
  ↓
Xianyu / Ali1688 / Taobao / Amazon / Xiaohongshu ...
```

产品路径的正确理解：

```text
Agent
  ↓
Tool / Port
  ↓
Crawler
  ↓
Browser Adapter
  ↓
具体 Browser
```

```text
Workflow
   ↓
Agent
   ↓
Tool Contract
   ↓
Tool Implementation
   ↓
Crawler / Browser
   ↓
Adapter
```

平台：

```text
Crawler Core
    ↑
Source Adapter
```

Browser：

```text
Browser Interface
    ↑
Playwright Adapter
    ↑
Camoufox Adapter
```

原则：高层依赖抽象，低层实现抽象。

---

## 前端拆分（packages/ + apps/）

应用装配在 `apps/web`（Vite 根，含 `index.html` / 路由表 / 页面）；可复用能力按业务域放 `packages/client/ui-*`。
没有 `src/` 了 —— 不要再往仓库根写前端代码。

参考 dsh 的是 **能力注入**，不是 Cordis 全家桶：

```text
Web 产品 UI（账号 / 爬虫 / 产品 Agent）
  ↓ HTTP
Python Server

Desktop 壳注入（仅客户端）
  · windowChrome
  · externalAgents（Codex/Claude/…）
  · 文件对话框 / 起停 Server
```

| 环境 | 产品 API | 外部 CLI Agent |
|------|----------|----------------|
| 浏览器 | 连本机 `VITE_API_BASE_URL` 或 `http://127.0.0.1:8787` | **不支持** |
| Tauri 客户端 | 壳注入 apiBaseUrl 后 HTTP | **支持**（`packages-rs/runtime/src/`） |

实现入口：`packages/client/runtime/src/capabilities.ts`。UI / 扫描 / Composer 用 `supportsExternalAgents()`，不要散落 `isTauri()` 冒充业务开关。

桌面适配器在 `packages/client/runtime/src/`（`server.ts`、`window.ts`、`capabilities.ts`）。
**禁止**新建 `packages/ui`、`packages/shared` 这类大杂烩包 —— 包名必须对应一个业务域（`ui-agent`）或一层机制（`runtime`）。

### 前端包依赖纪律（拆包后才看得见的三件事）

依赖必须单向：`apps/web → ui-* → ui-layout/ui-feedback → ui-primitives → ui-theme`，
叶子是 `app-state` / `runtime` / `routes` / `contracts`。

1. **叶子包不许引业务包。** `runtime` 曾经 `import "@v2/ui-crawler/discovery-scan"`，
   方向就反了。启动编排要组合多个域时，把它放到 `apps/web/src/boot/`。
2. **不要留「兼容旧 import」的转发壳。** 转发文件会让依赖图看起来多一条边
   （`ui-agent → ui-crawler`），把环藏起来。直接改调用方，删掉转发。
3. **跨域共享的 UI 状态放 `app-state`，不要寄居在某个业务包下。** 一旦寄居，
   那个包就被迫认识其它域。谁写状态谁留在自己域里（`ui-agent/agent-runtime-scan`、
   `ui-account/account-discovery`）。

新增包时**三处必须同时改**（根 `package.json` 依赖、根 `tsconfig.json` 的 `paths` 两条、
跑一次 `pnpm install`），详见 [`packages/README.md`](../../packages/README.md)。

---

## IPC 决策（本仓库）

Tauri 只是套壳。主要开发在 Web + Python。

**不要**为产品能力再开一套 Rust IPC，也**不要**单独新建 Rust crate / 二进制专门转发 Python。

### 两条通道，不要合成一条

| 通道 | 写在哪 | 干什么 |
|------|--------|--------|
| 产品 API | Python `server/src/api/` + `server/src/contracts/` | 账号、扫码、爬虫、产品 Agent、调研、MCP catalog、进度事件 |
| 壳 IPC | 现有 `packages-rs/client/src/commands/` | 只有浏览器/Python 做不了的事 |

React 产品调用形态：

```text
# Web（主开发）
apiBaseUrl = VITE_API_BASE_URL || http://127.0.0.1:8787
fetch(`${apiBaseUrl}/v1/...`)

# Desktop
invoke("get_server_status") → apiBaseUrl
fetch(`${apiBaseUrl}/v1/...`)
```

参考：`packages/client/runtime/src/capabilities.ts`、`runtime/src/server.ts`、`ui-account/src/account-store.ts`。

### 现有 Tauri command：留在 Rust，不要搬去 Python

| Command | 为什么必须是 Rust |
|---------|-------------------|
| `get_api_base_url` / `get_server_status` | 壳才知道 Python 进程起没起 |
| `pick_file` / `pick_folder` / `show_in_folder` | OS 对话框 / 资源管理器 |
| `list_agent_runtimes_command` / `probe_agent_runtime` / `login_agent_runtime` / `download_agent_runtime` | 读 PATH、探测登录、托管下载（不 spawn） |
| `log_frontend_error` | Python 未就绪时仍要落到壳日志 |

新增同类能力：加在 `packages-rs/client/src/commands/`，不要新开仓库或 `packages-rs/client/src/ipc/` 平行体系。

### 新产品能力：写 Python，不要写成 Tauri command

禁止：

```text
❌ invoke("search_products")
❌ invoke("agent_run")          // 产品 Agent
❌ invoke("save_snapshot")
❌ packages-rs/client 里再做一套 SQLite Repository 给爬虫/账号用
❌ Rust 把 HTTP 再包一层当网关
```

应该：

```text
✅ POST /v1/crawler/...
✅ POST /v1/agent/...           // 产品 Agent
✅ SSE / WebSocket（Python）推进度
✅ 账号/快照 SQLite 留在 Python infrastructure
```

产品 Agent 与外部 CLI 的流式输出都走 Python SSE（`/v1/agent/...`）。壳只做探测/下载，不要再 `emit("agent-event")` 起 CLI。

### SQLite 归属（覆盖通用模板）

通用分层常写「Rust 负责 SQLite」。**本仓库不采用。**

当前事实：`server/src/infrastructure/db/` → `~/.dingda/v2/dingda.db`。产品数据跟 Python 走，壳才像壳。

仍必须遵守：

- Agent / Crawler Core / Browser **不直接** `import sqlite3`，也不直接 import `src.infrastructure.db`。
- 持久化经 domain service 或显式 Port（例如 `SnapshotStore`）。
- Python 不操作「Rust 的 Repository」——因为产品库根本不在 Rust。

### React 禁止事项

- 不直连 Playwright / Camoufox / SQLite。
- 不 import Python。
- 不把产品请求改成「全部走 Rust 再转 Python」。

---

## 核心原则

1. Agent 不直接依赖 Playwright / Camoufox。
2. Agent 不直接访问 SQLite。
3. Agent 不直接操作具体电商平台。
4. Crawler 不应该包含 Agent 的决策逻辑。
5. Browser 是执行基础设施，不是业务逻辑。
6. Source 是平台适配层。
7. 新增一个电商平台时，原则上只需要新增 Source，不应该修改 Agent Core。
8. 新增一种浏览器实现时，不应该修改 Agent。
9. Tool 是 Agent 与底层能力之间的边界。
10. 所有跨模块通信必须使用明确的输入/输出 Schema。
11. 不允许为了方便直接跨层 import。
12. 不允许把所有逻辑堆到 `runtime/`、`utils/`、`services/` 等垃圾桶目录。

---

## 目标目录（新代码写这里）

```text
server/src/agent/core/
server/src/agent/workflows/
server/src/tools/                 # Tool 边界（不要再做一套 agent/tools 实现）
server/src/crawler/core/
server/src/crawler/sources/<platform>/
server/src/crawler/extraction/
server/src/crawler/snapshot/
server/src/crawler/dedup/
server/src/browser/               # manager / session / context / adapters
```

这些目录是新产品能力落点：

- `server/src/agent/`（勿再堆 `domains/agent`）
- `server/src/crawler/`（勿再堆 `domains/crawler`）
- `server/src/browser/`
- `server/src/tools/`（待建 Tool 契约）

`api/` 只做 HTTP 校验与调用；`domains/account`、`domains/channel`、`channels/` 继续承担账号/登录/IM，不要改成 Crawler Source。

---

## 目录词汇（只有职责真不同才建）

| 词 | 本仓库含义 |
|----|------------|
| core | 稳定生命周期与模型，不含平台/浏览器品牌 |
| source | 一个电商平台的抓取适配 |
| adapter | 一个外部实现（Playwright、Camoufox、vendor） |
| tool | Agent 可调用的契约 + 实现 |
| workflow | 业务流程编排（Research / 比价 / 选品） |
| infrastructure | 进程级 DB / EventBus，不是业务 |

不要为了目录数量拆 `application/`、`domain/`、`usecase/` 等空壳层。

### 垃圾桶目录

```text
❌ utils/ helpers/ common/ misc/ services/
❌ runtime/all_services.py
❌ 继续膨胀 packages/client/ui-primitives/src/utils.ts（前端 cn() 的唯一去处）
❌ 继续膨胀 server/src/shared/（仅 AppError）
❌ 继续膨胀 server/src/core/（仅 config/logging/lifespan/exceptions）
```

若确需 `utils`：只能放无业务、无 I/O、可单测的纯函数，并在模块文档写明边界。否则内联或放到真正的职责目录。

---

## 禁止依赖

```text
❌ Agent → XianyuCrawler
❌ Agent → Playwright / Camoufox
❌ Agent → sqlite3 / infrastructure.db
❌ Workflow → Camoufox
❌ Crawler Core → 某平台 special case
❌ React → Python 模块 / Browser 驱动
```

```text
✅ Agent → Tool Contract
✅ Tool Implementation → Crawler Port / Browser Port
✅ Crawler Source → Browser Port
✅ Browser Interface ← CamoufoxAdapter
```

---

## 契约

跨模块必须有输入/输出 Schema（Pydantic 或与前端共享的 TS 类型）。

| 面 | 契约位置 |
|----|----------|
| 产品 HTTP | `server/src/contracts/` ↔ `packages/contracts/src/` |
| CLI Agent 事件 | Python SSE ↔ `packages/contracts/src/agent-event.ts`（壳探测不推事件） |
| Tool | `server/src/tools/`（产品 Agent 与 MCP 共用；每工具一文件 + registry） |

改产品 API：**先契约，再 Python，再 React**。不必为了产品 HTTP 改 Rust。

改 CLI Runtime：**探测/下载**改 Tauri；**启动/流式**改 Python `cli` + `/v1/agent/runtimes/...`，再接 React。

---

## Channel ≠ Source ≠ Browser

| 模块 | 路径 | 做什么 |
|------|------|--------|
| Channel | `server/src/channels/` | 扫码、cookie、登录态、IM WSS |
| Crawler Source | `server/src/crawler/sources/` | 搜品、详情、平台解析 |
| Browser | `server/src/browser/` | Page/Cookie/导航/DOM |

闲鱼搜索逻辑不要写进 `channels/xianyu/`。扫码不要写进 `crawler/sources/xianyu/`。

---

## 目录级反例

```text
❌ agent/xianyu.py
❌ crawler/playwright.py
❌ runtime/all_services.py
❌ utils/everything.py
❌ domains/agent/service.py 变成上帝对象
```

```text
✅ server/src/agent/core/…
✅ server/src/crawler/sources/xianyu/crawler.py
✅ server/src/browser/adapters/camoufox.py
✅ server/src/tools/search.py
```
