# packages/client/ui-crawler

采集域：商品详情拉取与商品预览浮层。

包名 `@v2/ui-crawler`。

> 这个包原先还有一套「爬虫搜索台」（`CrawlerHub` 平台标签 + 关键词搜索 + 结果卡片）。
> 该页已被商品监控页（`@v2/ui-monitor`）取代，组件与配套的 SSE 搜品接口一并删除。
> 详见下方「曾经住在这里、现已迁出」。

## 文件

- `src/crawler-api.ts` — HTTP：`fetchCrawlerProduct`（单品详情，`POST /v1/crawler/product`）。
- `src/product-preview.ts` — 商品预览状态机：订阅 / 打开 / 关闭 + 系统浏览器外链。

## 消费方式

`package.json` exports 是 `{ "./*": "./src/*" }`，**没有包入口**：
应用层不需要装配本包的任何东西（原先要装配的 `CrawlerHub` 已随爬虫页删除），
所以不保留 `index.ts` —— 空入口和转发壳一样是债。

- **子路径** `@v2/ui-crawler/crawler-api` — `fetchCrawlerProduct`（`ui-ai` 的两个 PreviewDialog）
- **子路径** `@v2/ui-crawler/product-preview` — `subscribeProductPreview` / `openProductPreview` /
  `openProductInBrowserTab` / `closeProductPreviewUi`（`ui-ai` 多处）

## 依赖

- 工作区：`@v2/contracts` / `@v2/runtime`
- 外部：`@tauri-apps/plugin-opener`
- peer：`react`

## 曾经住在这里、现已迁出

- `crawler-hub.tsx` / `crawler-results.tsx` / `mock-data.ts` — 爬虫搜索台，
  被商品监控页取代（2026-09-14）。采集仍然在（后端 `/v1/crawler/*` 与 Agent 选品都在用），
  只是「人在页面上手输关键词搜」这条路径被「挑商品加监控」替代了。
- `crawler-api.ts` 的 SSE 部分（`searchCrawlerProductsLive` / `fetchCrawlerProductLive`）——
  前者唯一消费者是爬虫搜索台，后者从未接线。
- `discovery-scan.ts` → 按归属拆开：Agent 部分进 `@v2/ui-agent/cli/scan`，
  账号部分进 `@v2/ui-account/account-discovery`，跨域的启动编排进 `apps/web/src/boot`。
- `discovery-store.ts` → 下沉为 `@v2/app-state`。

原因：这份「发现层」是跨域编排，却被放在采集域里，导致
`ui-agent ↔ ui-crawler` 成环、`@v2/runtime` 反向依赖本包。
**采集域只该管采集**，不要因为「顺手」把跨域逻辑留在这里。

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
