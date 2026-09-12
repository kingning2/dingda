/**
 * 前端 Agent 运行阶段。
 *
 * 后端事件负责推进阶段；组件只读取这里的状态和映射，
 * 不再通过“最后一个块是什么”猜测当前应该展示什么。
 */

export type AgentRunPhase =
  | "starting"
  | "thinking"
  | "executing"
  | "outputting"
  | "live"
  | "products"
  | "completed"
  | "failed";

export interface AgentRunPhaseView {
  /** 对外持久化的状态值，保持 running / ready / error 兼容。 */
  statusState: string;
  /** 全局状态标签。 */
  label: string;
  /** 全局状态提示。 */
  hint: string | null;
  /** 状态徽标样式，保持和后端 DTO 的 badge_class 形状一致。 */
  badgeClass: string;
  /** 没有活跃正文/思考片段时，时间线底部展示的工作文案。 */
  workingLabel: string | null;
  /** 当前阶段真正处于流入状态的块类型。 */
  streamingKind: "thinking" | "text" | null;
  /** 思考阶段隐藏尚未被后续事件替代的正文。 */
  hideTextWhileThinking: boolean;
}

/**
 * Agent 运行阶段到 UI 的唯一映射。
 *
 * 新增阶段时只改这里，避免状态判断散落在 reducer、scheduler 和块组件中。
 */
export const AGENT_RUN_PHASE_MAP: Record<AgentRunPhase, AgentRunPhaseView> = {
  starting: {
    statusState: "running",
    label: "Starting",
    hint: "Agent 启动中…",
    badgeClass: "bg-sky-500/15 text-sky-700",
    workingLabel: "Starting",
    streamingKind: null,
    hideTextWhileThinking: false,
  },
  thinking: {
    statusState: "running",
    label: "Thinking",
    hint: "模型推理中…",
    badgeClass: "bg-amber-500/15 text-amber-700",
    workingLabel: "Thinking",
    streamingKind: "thinking",
    hideTextWhileThinking: true,
  },
  executing: {
    statusState: "running",
    label: "Working",
    hint: "工具执行中…",
    badgeClass: "bg-sky-500/15 text-sky-700",
    workingLabel: "Working",
    streamingKind: null,
    hideTextWhileThinking: false,
  },
  outputting: {
    statusState: "running",
    label: "Responding",
    hint: "正文生成中…",
    badgeClass: "bg-emerald-500/15 text-emerald-600",
    workingLabel: null,
    streamingKind: "text",
    hideTextWhileThinking: false,
  },
  live: {
    statusState: "running",
    label: "Browsing",
    hint: "浏览器页面直播中…",
    badgeClass: "bg-rose-500/15 text-rose-600",
    workingLabel: "Browsing",
    streamingKind: null,
    hideTextWhileThinking: false,
  },
  products: {
    statusState: "running",
    label: "Collecting results",
    hint: "商品结果已更新",
    badgeClass: "bg-emerald-500/15 text-emerald-600",
    workingLabel: "Collecting results",
    streamingKind: null,
    hideTextWhileThinking: false,
  },
  completed: {
    statusState: "ready",
    label: "Completed",
    hint: null,
    badgeClass: "bg-emerald-500/15 text-emerald-600",
    workingLabel: null,
    streamingKind: null,
    hideTextWhileThinking: false,
  },
  failed: {
    statusState: "error",
    label: "Failed",
    hint: null,
    badgeClass: "bg-red-500/15 text-red-700",
    workingLabel: null,
    streamingKind: null,
    hideTextWhileThinking: false,
  },
};
