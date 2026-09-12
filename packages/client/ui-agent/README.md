# packages/client/ui-agent

Agent 域：外部 CLI Runtime 探测与运行态。

包名 `@v2/ui-agent`。

## 文件

- `src/agent-api.ts`
- `src/agent-catalog.ts`
- `src/agent-event-reducer.ts`
- `src/agent-icon.tsx`
- `src/agent-run-phase.ts`
- `src/agent-run.ts`
- `src/agent-runtime-card.tsx`
- `src/agent-runtime-scan.ts`
- `src/agent-runtime.ts`
- `src/agent-runtimes-panel.tsx`
- `src/index.ts`

## 依赖

- 工作区：@v2/app-state / @v2/contracts / @v2/runtime / @v2/ui-primitives
- 外部：@tauri-apps/api / lucide-react
- peer：react

## 发现逻辑归本域

`src/agent-runtime-scan.ts` 是 Agent 运行时发现的实现（读 SQLite 缓存 → 后台补探测 →
手动全量扫描），写 `@v2/app-state` 的 agents / recentWorks 两个切片。

它早先只是 `@v2/ui-crawler/discovery-scan` 的转发壳，导致 `ui-agent ↔ ui-crawler` 成环。
**不要再为「兼容旧 import」建转发文件**，直接改调用方。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
