# packages/client/ui-monitor

商品监控域：监控列表、价格历史与变更事件。

包名 `@v2/ui-monitor`。

监控的商品由用户自己挑：从 Agent 选品结果一键加入，或在监控页手填平台 + 商品 ID。
后台调度器（`packages-py/domains/watch/scheduler.py`）每 6 小时轮询一次并落价格点。

## 文件

- `src/index.ts` — 包入口，暴露 `MonitorHub`（页面级装配）。
- `src/monitor-hub.tsx` — 页面装配：左列表 + 右详情；持有列表/选中项/详情三份状态。
- `src/monitor-list.tsx` — 目标列表：标题、现价、涨跌、售出态徽标。
- `src/monitor-detail.tsx` — 详情：快照指标 + 变更记录 + 价格历史点，含暂停/恢复/移除。
- `src/monitor-add-form.tsx` — 「加入监控」按钮 + 弹窗（平台 Select + 商品 ID Input）。
- `src/monitor-api.ts` — HTTP：`/v1/watch` 的列表/加入/详情/调整/移除五个端点。
- `src/monitor-format.ts` — 展示口径纯函数：状态文案、涨跌串、价格/时间/间隔格式化。
- `src/monitor-item-id.ts` — 输入归一：从粘贴的链接里取出商品 ID。
- `src/monitor-platforms.ts` — 可加入监控的平台词表 + `platformLabel`。

## 消费方式

`package.json` exports 是 `{ ".": "./src/index.ts", "./*": "./src/*" }`：

- **包入口** `@v2/ui-monitor` — `MonitorHub`（`apps/web/src/pages/monitor-page.tsx`）
- **子路径** `@v2/ui-monitor/monitor-api` — `addMonitorTargets`（`@v2/ui-ai/panel/products` 的「加入监控」按钮）

## 与后端的口径分工

- **涨跌由后端算**：`price_drop` = 首价 − 现价，正数表示已降价。前端不重新比较首价与现价 ——
  两边各算一份，一旦对不上就无从判断谁对。
- **状态字段是自由字符串**：`sold_state` / `state` / `kind` 的值域由 Python 侧
  `contracts.watch` 保证。前端一律容错映射，未收录的值**原样回显**而不是塞「未知」——
  否则新状态上线时前端会静默说谎。
- **变更文案由后端给**（`MonitorChangeItem.message`），前端只加一个类型徽标，不重拼。

## 刻意没做的

- **价格折线图**：价格点少、横轴时间不等距，折线会误导。等点够密再考虑。
- **前端轮询**：后台调度器每 6 小时才写一次库，前端跟着轮询只是白打后端。
- **概览卡片与手动刷新**：`/v1/watch/summary` 与 `/v1/watch/poll` 后端有，本轮前端不调，
  故 `packages/contracts/src/monitor.ts` 也没声明它们的类型。

## 依赖

- 工作区：`@v2/contracts` / `@v2/runtime` / `@v2/ui-primitives`
- 外部：`lucide-react`
- peer：`react`

## 边界

改本包前先看仓库根的 [AGENTS.md](../../../AGENTS.md) 与 [.agents/skills/layers.md](../../../.agents/skills/layers.md)。
上层 README 只链接下层；本包不反向依赖上层。
