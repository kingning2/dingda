# packages/client/ui-crawler

采集域：采集台、结果展示、实时发现。

包名 `@v2/ui-crawler`。

## 文件

- `src/crawler-api.ts`
- `src/crawler-hub.tsx`
- `src/crawler-results.tsx`
- `src/discovery-scan.ts`
- `src/discovery-store.ts`
- `src/index.ts`
- `src/mock-data.ts`
- `src/product-preview.ts`

## 依赖

- 工作区：@v2/contracts / @v2/runtime / @v2/ui-account / @v2/ui-agent / @v2/ui-primitives
- 外部：@tauri-apps/plugin-opener / lucide-react / zustand
- peer：react

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
