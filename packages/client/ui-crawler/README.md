# packages/client/ui-crawler

采集域：采集台、结果展示、商品预览。

包名 `@v2/ui-crawler`。

## 文件

- `src/crawler-api.ts`
- `src/crawler-hub.tsx`
- `src/crawler-results.tsx`
- `src/index.ts`
- `src/mock-data.ts`
- `src/product-preview.ts`

## 依赖

- 工作区：`@v2/contracts` / `@v2/runtime` / `@v2/ui-primitives`
- 外部：`@tauri-apps/plugin-opener` / `lucide-react`
- peer：`react`

## 曾经住在这里、现已迁出

- `discovery-scan.ts` → 按归属拆开：Agent 部分进 `@v2/ui-agent/agent-runtime-scan`，
  账号部分进 `@v2/ui-account/account-discovery`，跨域的启动编排进 `apps/web/src/boot`。
- `discovery-store.ts` → 下沉为 `@v2/app-state`。

原因：这份「发现层」是跨域编排，却被放在采集域里，导致
`ui-agent ↔ ui-crawler` 成环、`@v2/runtime` 反向依赖本包。
**采集域只该管采集**，不要因为「顺手」把跨域逻辑留在这里。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
