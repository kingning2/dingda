import { listenEvent } from "./index";

export const MONITOR_MATCH_EVENT = "app/monitor";

export interface MonitorMatchPayload {
  category: "monitor_match";
  taskId: string;
  taskName: string;
  itemId: string;
  title: string;
  url: string;
  priceText: string;
  reason: string;
}

export function listenMonitorMatch(
  handler: (payload: MonitorMatchPayload) => void,
) {
  return listenEvent<MonitorMatchPayload>(MONITOR_MATCH_EVENT, handler);
}

export const MONITOR_PROGRESS_EVENT = "app/monitor/progress";

export type MonitorProgressStage =
  | "started"
  | "keywords"
  | "search"
  | "scanned"
  | "decide"
  | "matched"
  | "finished"
  | "failed";

export interface MonitorProgressSummary {
  scanned: number;
  newItems: number;
  skipped: number;
  recommended: number;
}

/** 单条运行步骤（已持久化的运行记录 steps 使用，无 category）。 */
export interface MonitorStepPayload {
  /** 步骤唯一 id — Rust 流式事件携带，用于前端稳定渲染与去重。 */
  stepId?: string;
  runId: string;
  taskId: string;
  taskName: string;
  stage: MonitorProgressStage;
  message: string;
  detail?: string;
  summary?: MonitorProgressSummary;
  /** 正文（发给 AI 的 prompt / AI 原始返回 / 爬取文本）。 */
  content?: string;
  /** 正文类型。 */
  contentKind?: "json" | "markdown" | "text";
  /** 说话角色：发送给 AI / AI 返回 / 爬虫。 */
  role?: "user" | "assistant" | "tool";
}

/** 实时进度事件（Tauri 事件带 category 标记）。 */
export interface MonitorProgressPayload extends MonitorStepPayload {
  category: "monitor_progress";
}

export function listenMonitorProgress(
  handler: (payload: MonitorProgressPayload) => void,
) {
  return listenEvent<MonitorProgressPayload>(MONITOR_PROGRESS_EVENT, handler);
}
