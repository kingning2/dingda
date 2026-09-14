# packages/client/ui-agent

Agent 域：外部 CLI Runtime 探测与运行态。

包名 `@v2/ui-agent`。

## 文件

- `src/index.ts` — 包入口。**当前只暴露 `AgentRuntimesPanel`**（`apps/web` 装配页面用）。
  其余符号由消费方按子路径直取，见下「消费方式」。不要往这里加转发导出。

- `src/agent-runtimes-panel.tsx` — Agent 页主面板 `AgentRuntimesPanel`：把 agents 分成
  「已检测到 / 未安装」两组渲染卡片，承接**扫描、登录、下载、设为默认、改模型**五个动作，
  动作结果统一落在 `actionHint` 上展示。
  调用：`agent-runtime-scan`（rescan / probeSingleAgent）、`agent-runtime`（login / download /
  applyAgentPreferences）、`agent-api`（putDefaultAgentId / putDefaultModelId）、`agent-runtime-card`。
  被 `src/index.ts` 使用。

- `src/agent-runtime-card.tsx` — 单个 Agent 的配置卡 `AgentRuntimeCard`：图标 + 状态徽标 + 鉴权徽标 +
  下一步提示 + 模型下拉 + 下载进度条 + 动作按钮。
  `resolveSetupPhase()` 把 catalog 与 probe 字段收成 `missing / probing / needs_auth / ready`
  四种阶段，**不按 Agent 特判**；按钮显隐全由阶段推导。
  被 `src/agent-runtimes-panel.tsx` 使用。

- `src/agent-icon.tsx` — Agent 图标 `AgentIcon`：按 id 选 `.svg` / `.png`；`MONO_ICONS` 里的单色图标
  走 CSS mask 跟随文字色；表里没有的 id 回落成首字母方块。
  被 `src/agent-runtime-card.tsx`、`ui-ai/src/Settings.tsx`、`ui-composer/src/composer-agent-picker.tsx` 使用。

- `src/agent-runtime.ts` — 外部 CLI Runtime 的**探测与操作**：PATH 探测、鉴权视图组装、后台并发
  probe、登录、下载，外加数据规整与浏览器 mock。
  **432 行 / 14 个顶层导出，混装四类职责（探测 / 鉴权 / 下载 / mock），待拆 —— 见下「已知结构问题」。**
  被 `agent-runtime-scan.ts`、`agent-runtime-card.tsx`、`agent-runtimes-panel.tsx` 使用。

- `src/agent-runtime-scan.ts` — 运行时发现编排：读 SQLite 缓存 → 后台补探测 → 用户手动全量扫描。
  写 `@v2/app-state` 的 agents / recentWorks 切片；`mergeCatalogCoverage()` 保证旧缓存缺新 Agent
  时卡片不消失。
  被 `apps/web/src/boot/preload.ts`（子路径）与 `src/agent-runtimes-panel.tsx` 使用。

- `src/agent-catalog.ts` — 对外暴露的本地 Agent CLI 目录 `AGENT_CATALOG`，与后端 `AGENT_REGISTRY`、
  Rust `RUNTIME_REGISTRY` 对齐。**同时是「支持的 Agent 白名单」**（`SUPPORTED_AGENT_IDS` 由它派生）。
  被 `src/agent-runtime-scan.ts` 使用。

- `src/agent-api.ts` — Agent 域的 Server HTTP：偏好读写、扫描目录读写、工作会话读写。
  **全部走 `@v2/runtime/http-client`**，不自己拼 baseUrl。
  被 `src/agent-runtime.ts`、`src/agent-runtime-scan.ts`、`ui-ai/src/session.ts`、`ui-ai/src/layout.tsx` 使用。

- `src/agent-run.ts` — 一次外部 CLI 运行：`POST /v1/agent/runtimes/{id}/run` 收 SSE 流，逐个事件回调。
  这里**必须裸 `fetch`**：统一 http-client 会一次性读完整个响应，做不了流式（见文件内注释）。
  被 `ui-ai/src/send.ts` 使用。

- `src/agent-run-phase.ts` — 运行阶段到 UI 的**唯一映射** `AGENT_RUN_PHASE_MAP`：阶段、徽标样式、
  流式块类型、思考期是否隐藏正文。新增阶段只改这里。
  被 `src/agent-event-reducer.ts`、`ui-ai/src/chat/`（schedule / working-status / chat）、
  `ui-ai/src/layout.tsx` 使用。

- `src/agent-event-reducer.ts` — 把 SSE 事件折叠成助手消息状态：时间线按到达顺序交错（思考 ↔ 工具 ↔
  正文）、步骤 upsert / patch、阶段推进、乐观发送、按用户消息截断。
  被 `ui-ai/src/send.ts`、`ui-ai/src/layout.tsx` 使用。

## 消费方式（子路径 vs 包入口）

`package.json` 的 `exports` 是 `{ ".": "./src/index.ts", "./*": "./src/*" }`，两种取法并存：

- **包入口** `@v2/ui-agent` —— 当前只有 `AgentRuntimesPanel` 走这里（`apps/web/src/pages/agents-page.tsx`）
- **子路径** `@v2/ui-agent/<file>` —— `agent-runtime-scan`（preload）、`agent-api`（ui-ai）、
  `agent-run` / `agent-event-reducer`（ui-ai/send）、`agent-run-phase`（ui-ai/chat）、
  `agent-icon`（ui-ai、ui-composer）

新增消费方时**按需选一种，不要两种都留**；包内互相引用一律走相对路径，不要绕回包入口。

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/runtime / @v2/ui-primitives
- 外部：@tauri-apps/api / lucide-react
- peer：react

## 发现逻辑归本域

`src/agent-runtime-scan.ts` 是 Agent 运行时发现的实现（读 SQLite 缓存 → 后台补探测 →
手动全量扫描），写 `@v2/app-state` 的 agents / recentWorks 两个切片。

它早先只是 `@v2/ui-crawler/discovery-scan` 的转发壳，导致 `ui-agent ↔ ui-crawler` 成环。
**不要再为「兼容旧 import」建转发文件**，直接改调用方。

## 已知结构问题（待重构）

1. `src/agent-runtime.ts`（432 行 / 14 导出）混装四类职责，按
   [frontend-coding](../../../.agents/skills/frontend-coding/SKILL.md) 应拆为
   `cli/{probe,login,download,normalize}.ts`。
2. `src/index.ts` 的 6 个导出里只有 `AgentRuntimesPanel` 被包入口消费，其余 5 个是冗余转发壳。
3. `agent-runtime.ts` 里的浏览器 mock（`mockCodexAuthenticated` / `mockClaudeAuthenticated` /
   `delay`）与生产代码混装，违反 `frontend-architecture` 反例第 6 条。

施工图见 `.workbuddy-ai/outputs/ui-agent-refactor-plan.md`。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
