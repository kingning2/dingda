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

- 工作区：@v2/contracts / @v2/runtime / @v2/ui-crawler / @v2/ui-primitives
- 外部：@tauri-apps/api / lucide-react
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
