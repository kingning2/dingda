# packages/client/ui-agent

Agent 域：产品 Agent（内置 dingda）的运行态与最近工作。

包名 `@v2/ui-agent`。外部 CLI Runtime（codex / claude / opencode）已整体移除，
本包不再有探测 / 登录 / 下载 / 目录逻辑。

## 目录

```text
src/
  index.ts              包入口（仅说明文档；导出面见「消费方式」）
  status-tone.ts        状态徽标六档语义色常量
  api.ts                Agent 域 Server HTTP（工作会话读写）
  recent-works.ts       最近工作列表刷新
  run/
    stream.ts           SSE 收发（裸 fetch，统一 http-client 做不了流式）
    phase.ts            运行阶段到 UI 的唯一映射 AGENT_RUN_PHASE_MAP
    reducer.ts          SSE 事件折叠成助手消息状态
```

## 文件说明

- `src/index.ts` — 包入口。**不含运行时代码**，只作包说明；其余符号由消费方按
  子路径直取，见下「消费方式」。不要往这里加转发导出。

- `src/api.ts` — Agent 域的 Server HTTP：工作会话读写（fetch / patch / runs）。
  **全部走 `@v2/runtime/http-client`**，不自己拼 baseUrl。
  被 `ui-ai/src/session.ts`、`ui-ai/src/layout.tsx` 使用。

- `src/recent-works.ts` — `refreshRecentWorks()`：拉最近工作列表写进
  `@v2/app-state` 的 recentWorks 切片。被 `apps/web/src/boot/preload.ts` 使用。

- `src/run/stream.ts` — 一次产品 Agent 运行：`POST /v1/agent/works/{workId}/run` 收 SSE 流，
  逐个事件回调；取消即 abort 底层 fetch（服务端继续跑完落库，UI 丢弃后续事件）。
  这里**必须裸 `fetch`**：统一 http-client 会一次性读完整个响应，
  做不了流式（见文件内注释）。
  被 `ui-ai/src/send.ts` 使用。

- `src/run/phase.ts` — 运行阶段到 UI 的**唯一映射** `AGENT_RUN_PHASE_MAP`：阶段、徽标样式、
  流式块类型、思考期是否隐藏正文。新增阶段只改这里。
  被 `reducer.ts`、`ui-ai/src/chat/`（schedule / working-status / chat / chat-turn）、
  `ui-ai/src/layout.tsx`、`ui-ai/src/send.ts` 使用。

- `src/run/reducer.ts` — 把 SSE 事件折叠成助手消息状态：时间线按到达顺序交错（思考 ↔ 工具 ↔
  正文）、步骤 upsert / patch、阶段推进、乐观发送、按用户消息截断。
  被 `ui-ai/src/send.ts`、`ui-ai/src/layout.tsx` 使用。

- `src/status-tone.ts` — 状态徽标六档语义色常量 `STATUS_TONE`：neutral / active / ready /
  live / pending / failed。被 `run/` 使用。

## 消费方式（子路径 vs 包入口）

`package.json` 的 `exports` 是 `{ ".": "./src/index.ts", "./*": "./src/*" }`，两种取法并存：

- **包入口** `@v2/ui-agent` —— 仅作说明文档，不含运行时导出
- **子路径** `@v2/ui-agent/<dir>/<file>` —— `api`（ui-ai/session、layout）、
  `recent-works`（preload）、`run/stream` / `run/reducer`（ui-ai/send）、
  `run/phase`（ui-ai/chat）

新增消费方时**按需选一种，不要两种都留**；包内互相引用一律走相对路径，不要绕回包入口。

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/runtime / @v2/ui-primitives
- 外部：@tauri-apps/api / lucide-react
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md)（第 2 节分层规则）。
上层 README 只链接下层；本包不反向依赖上层。
