/**
 * 商品监控域：监控列表、价格历史与变更事件。
 *
 * 包入口只暴露 `WatchHub`（页面级装配）。
 * 「加入监控」这个跨域动作由子路径 `@v2/ui-watch/watch-api` 暴露给 Agent 选品结果，
 * 不从这里转发 —— 按仓库约定，不为跨域调用留转发壳。
 */

export { WatchHub } from "./watch-hub";
