/**
 * 包入口。
 *
 * 职责：
 *   给应用层（apps/web）提供 Agent 页的面板组件。
 *
 * 设计说明：
 *   - 按 `frontend-coding`，包入口**只暴露应用层要装配的东西**。其余符号一律走子路径
 *     （`@v2/ui-agent/<file>`）按需引用 —— 在这里再转发一遍会让「谁认识谁」不可查，
 *     也会把依赖图的边藏进转发层里（`ui-agent/README.md` 记过这个坑）。
 *   - 因此本文件只有一行。加导出前先问：应用层装配真的需要它吗？
 */

export { AgentRuntimesPanel } from "./agent-runtimes-panel";
