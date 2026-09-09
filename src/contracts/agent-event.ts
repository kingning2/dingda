/** 统一 Agent 事件 — Python SSE 与前端 reducer 共用。
 * 聊天块由后端下发的 step / page 驱动；前端只 upsert，不猜 kind。
 */

import type { AgentWorkStepPageView, AgentWorkStepView } from "./ai-work";

/** 后端下发的步骤快照（可与 AgentWorkStepView 对齐）。 */
export type AgentStepPayload = AgentWorkStepView;

export type AgentEvent =
  | { type: "runStarted"; runtimeId: string; runId: string }
  | { type: "textDelta"; text: string }
  | { type: "thinking"; text: string }
  | {
      type: "toolCall";
      id: string;
      name: string;
      input: unknown;
      /** 后端已决定的步骤块；有则前端直接 upsert */
      step?: AgentStepPayload;
    }
  | {
      type: "toolResult";
      id: string;
      output: unknown;
      step?: Partial<AgentStepPayload> & { id: string; page_loading?: boolean };
    }
  | {
      type: "browserFrame";
      url: string;
      title: string;
      hint?: string | null;
      screenshot_url: string;
      /** 后端 page 快照，挂到进行中的 browser_crawl */
      page?: AgentWorkStepPageView;
    }
  | { type: "fileChanged"; path: string }
  | { type: "session"; sessionId: string }
  | { type: "error"; message: string }
  | { type: "runCompleted"; exitCode: number };

export type AgentEventEnvelope = { runId: string } & AgentEvent;

export function isAgentEventEnvelope(value: unknown): value is AgentEventEnvelope {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return typeof record.runId === "string" && typeof record.type === "string";
}

export function parseAgentEventEnvelope(raw: unknown): AgentEventEnvelope | null {
  if (!isAgentEventEnvelope(raw)) return null;
  return raw;
}
