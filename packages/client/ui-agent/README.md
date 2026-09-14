# packages/client/ui-agent

Agent 域：外部 CLI Runtime 探测与运行态。

包名 `@v2/ui-agent`。

## 目录

```text
src/
  index.ts              包入口（只暴露 AgentRuntimesPanel）
  status-tone.ts        状态徽标六档语义色常量
  api.ts                Agent 域 Server HTTP（偏好 / 目录 / 工作会话）
  agent-catalog.ts      对外暴露的本地 Agent CLI 目录 AGENT_CATALOG（支持白名单）
  cli/
    normalize.ts        数据规整：snake_case / camelCase 抹平、偏好叠加
    catalog.ts          拉取本地目录与注册表占位
    probe.ts            单个 / 后台批量探测、探测状态标记
    login.ts            拉起 CLI 登录
    download.ts         下载到托管目录
    auth-view.ts        鉴权视图组装与辅助判定
    scan.ts             发现编排：缓存 → 后台补探测 → 手动全量扫描
  run/
    stream.ts           SSE 收发（裸 fetch，统一 http-client 做不了流式）
    phase.ts            运行阶段到 UI 的唯一映射 AGENT_RUN_PHASE_MAP
    reducer.ts          SSE 事件折叠成助手消息状态
  ui/
    runtimes-panel.tsx  Agent 页主面板
    runtime-card.tsx    单个 Agent 的配置卡
    icon.tsx            Agent 图标
```

## 文件说明

- `src/index.ts` — 包入口。**只暴露 `AgentRuntimesPanel`**（`apps/web` 装配页面用）。
  其余符号由消费方按子路径直取，见下「消费方式」。不要往这里加转发导出。

- `src/cli/scan.ts` — 运行时发现编排：读 SQLite 缓存 → 后台补探测 → 用户手动全量扫描。
  写 `@v2/app-state` 的 agents / recentWorks 切片；`mergeCatalogCoverage()` 保证旧缓存缺新 Agent
  时卡片不消失。
  被 `apps/web/src/boot/preload.ts`（子路径）与 `src/ui/runtimes-panel.tsx` 使用。

- `src/cli/catalog.ts` — 拉取本地 Agent 目录（Tauri PATH 探测）与注册表占位。
  被 `scan.ts` 使用。

- `src/cli/probe.ts` — 探测单个 Agent、后台并发 probe、探测状态标记。
  被 `scan.ts`、`runtime-card.tsx` 使用。

- `src/cli/login.ts` — 拉起 CLI 登录。
  被 `runtimes-panel.tsx` 使用。

- `src/cli/download.ts` — 下载 Agent 到叮答托管目录。
  被 `runtimes-panel.tsx` 使用。

- `src/cli/normalize.ts` — 把后端 / Rust 返回的原始字段规整成 `AgentRuntimeItem`；
  将 SQLite 偏好盖到 `is_default` / `preferred_model_id`。
  被 `catalog.ts`、`scan.ts` 使用。

- `src/cli/auth-view.ts` — 根据探针结果组装统一鉴权视图；`getAgentGuideUrl` /
  `supportsAgentLogin` 辅助判定。
  被 `probe.ts`、`runtime-card.tsx` 使用。

- `src/run/stream.ts` — 一次外部 CLI 运行：`POST /v1/agent/runtimes/{id}/run` 收 SSE 流，
  逐个事件回调。这里**必须裸 `fetch`**：统一 http-client 会一次性读完整个响应，
  做不了流式（见文件内注释）。
  被 `ui-ai/src/send.ts` 使用。

- `src/run/phase.ts` — 运行阶段到 UI 的**唯一映射** `AGENT_RUN_PHASE_MAP`：阶段、徽标样式、
  流式块类型、思考期是否隐藏正文。新增阶段只改这里。
  被 `reducer.ts`、`ui-ai/src/chat/`（schedule / working-status / chat / chat-turn）、
  `ui-ai/src/layout.tsx`、`ui-ai/src/send.ts` 使用。

- `src/run/reducer.ts` — 把 SSE 事件折叠成助手消息状态：时间线按到达顺序交错（思考 ↔ 工具 ↔
  正文）、步骤 upsert / patch、阶段推进、乐观发送、按用户消息截断。
  被 `ui-ai/src/send.ts`、`ui-ai/src/layout.tsx` 使用。

- `src/ui/runtimes-panel.tsx` — Agent 页主面板 `AgentRuntimesPanel`：把 agents 分成
  「已检测到 / 未安装」两组渲染卡片，承接**扫描、登录、下载、设为默认、改模型**五个动作，
  动作结果统一落在 `actionHint` 上展示。
  被 `src/index.ts` 使用。

- `src/ui/runtime-card.tsx` — 单个 Agent 的配置卡 `AgentRuntimeCard`：图标 + 状态徽标 + 鉴权徽标 +
  下一步提示 + 模型下拉 + 下载进度条 + 动作按钮。
  `resolveSetupPhase()` 把 catalog 与 probe 字段收成 `missing / probing / needs_auth / ready`
  四种阶段，**不按 Agent 特判**；按钮显隐全由阶段推导。
  被 `runtimes-panel.tsx` 使用。

- `src/ui/icon.tsx` — Agent 图标 `AgentIcon`：按 id 选 `.svg` / `.png`；`MONO_ICONS` 里的单色图标
  走 CSS mask 跟随文字色；表里没有的 id 回落成首字母方块。
  被 `runtime-card.tsx`、`ui-ai/src/Settings.tsx`、`ui-composer/src/composer-agent-picker.tsx` 使用。

- `src/api.ts` — Agent 域的 Server HTTP：偏好读写、扫描目录读写、工作会话读写。
  **全部走 `@v2/runtime/http-client`**，不自己拼 baseUrl。
  被 `cli/scan.ts`、`cli/catalog.ts`、`ui-ai/src/session.ts`、`ui-ai/src/layout.tsx` 使用。

- `src/agent-catalog.ts` — 对外暴露的本地 Agent CLI 目录 `AGENT_CATALOG`，与后端 `AGENT_REGISTRY`、
  Rust `RUNTIME_REGISTRY` 对齐。**同时是「支持的 Agent 白名单」**（`SUPPORTED_AGENT_IDS` 由它派生）。
  被 `cli/scan.ts` 使用。

- `src/status-tone.ts` — 状态徽标六档语义色常量 `STATUS_TONE`：neutral / active / ready /
  live / pending / failed。被 `cli/`、`run/`、`ui/` 共用。

## 消费方式（子路径 vs 包入口）

`package.json` 的 `exports` 是 `{ ".": "./src/index.ts", "./*": "./src/*" }`，两种取法并存：

- **包入口** `@v2/ui-agent` —— 只有 `AgentRuntimesPanel` 走这里（`apps/web/src/pages/agents-page.tsx`）
- **子路径** `@v2/ui-agent/<dir>/<file>` —— `cli/scan`（preload）、`api`（ui-ai）、
  `run/stream` / `run/reducer`（ui-ai/send）、`run/phase`（ui-ai/chat）、
  `ui/icon`（ui-ai、ui-composer）

新增消费方时**按需选一种，不要两种都留**；包内互相引用一律走相对路径，不要绕回包入口。

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/runtime / @v2/ui-primitives
- 外部：@tauri-apps/api / lucide-react
- peer：react

## 发现逻辑归本域

`src/cli/scan.ts` 是 Agent 运行时发现的实现（读 SQLite 缓存 → 后台补探测 → 手动全量扫描），
写 `@v2/app-state` 的 agents / recentWorks 两个切片。

它早先只是 `@v2/ui-crawler/discovery-scan` 的转发壳，导致 `ui-agent ↔ ui-crawler` 成环。
**不要再为「兼容旧 import」建转发文件**，直接改调用方。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
