/**
 * 包入口。
 *
 * 职责：
 *   给应用层（apps/web）提供 Agent 页的面板组件。
 *
 * 设计说明：
 *   - 按 frontend-coding，包入口只应暴露应用层要装配的符号。当前还额外挂着
 *     AgentRuntimeCard / AGENT_CATALOG 与 5 个 scan 函数，属冗余转发壳，待删
 *     （见 README「已知结构问题」）
 */

export { AgentRuntimesPanel } from "./agent-runtimes-panel";
export { AgentRuntimeCard } from "./agent-runtime-card";
export { AGENT_CATALOG } from "./agent-catalog";
export {
  loadCachedAgentRuntimes,
  probeSingleAgent,
  refreshDefaultAgentPreference,
  refreshRecentWorks,
  rescanAgentRuntimes,
} from "./agent-runtime-scan";
