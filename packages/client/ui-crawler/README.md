# packages/client/ui-crawler

采集域：采集台、结果展示、商品预览。

包名 `@v2/ui-crawler`。

## 文件

- `src/index.ts` — 包入口，暴露 `CrawlerHub` / `CrawlerPanel` / `CrawlerResults` / `CrawlerStatusBanner`。
- `src/crawler-api.ts` — HTTP API：搜品、详情、直播流（SSE）。
  - 搜品/详情走统一 http-client；直播流必须裸 `fetch`（统一客户端做不了 SSE）。
- `src/crawler-hub.tsx` — 页面级装配：`CrawlerHub`（平台标签切换）+ `CrawlerPanel`（单平台搜索）。
- `src/crawler-results.tsx` — 结果展示：`CrawlerResults`（商品卡片列表）+ `CrawlerStatusBanner`（状态横幅）。
- `src/product-preview.ts` — 商品预览状态机：订阅/打开/关闭 + 浏览器外链。
- `src/mock-data.ts` — 支持的平台标签常量 `CRAWL_PLATFORM_TABS`。

## 消费方式

`package.json` exports 是 `{ ".": "./src/index.ts", "./*": "./src/*" }`：

- **包入口** `@v2/ui-crawler` — `CrawlerHub`（`apps/web/src/pages/crawler-page.tsx`）
- **子路径** `@v2/ui-crawler/crawler-api` — `fetchCrawlerProduct`（两个 PreviewDialog）
- **子路径** `@v2/ui-crawler/product-preview` — `subscribeProductPreview` / `openProductPreview` / `openProductInBrowserTab`（ui-ai 多处）

## 依赖

- 工作区：`@v2/contracts` / `@v2/runtime` / `@v2/ui-primitives`
- 外部：`@tauri-apps/plugin-opener` / `lucide-react`
- peer：`react`

## 曾经住在这里、现已迁出

- `discovery-scan.ts` → 按归属拆开：Agent 部分进 `@v2/ui-agent/cli/scan`，
  账号部分进 `@v2/ui-account/account-discovery`，跨域的启动编排进 `apps/web/src/boot`。
- `discovery-store.ts` → 下沉为 `@v2/app-state`。

原因：这份「发现层」是跨域编排，却被放在采集域里，导致
`ui-agent ↔ ui-crawler` 成环、`@v2/runtime` 反向依赖本包。
**采集域只该管采集**，不要因为「顺手」把跨域逻辑留在这里。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
