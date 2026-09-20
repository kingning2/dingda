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
      /** 该帧来自哪个子会话；有值时应挂进对应子块而不是父的平铺步骤 */
      childRunId?: string;
      /**
       * 该帧挂到哪个步骤块；不填则：登录帧优先挂进行中的 login，
       * 其它帧挂当前进行中的 browser_crawl。
       * 掉线恢复要填：那时搜索块还在跑，二维码会被它抢走。
       */
      stepId?: string;
    }
  | { type: "error"; message: string }
  | { type: "runCompleted"; exitCode: number }
  | {
      type: "agentPhase";
      runId: string;
      role: "parent" | "worker" | "child" | string;
      phase: string;
      parentRunId?: string | null;
      sessionId?: string | null;
      step?: string | null;
      errorCode?: string | null;
      /** 子会话收尾摘要，服务端定相时一并下发 */
      summary?: string | null;
    }
  | {
      /**
       * 子会话事件中继信封：Server 把 worker 的事件按原样包一层推给父 run。
       * 前端据此把子会话的步骤/正文收进嵌套子块，而不是父的平铺步骤。
       */
      type: "childEvent";
      childRunId: string;
      role: string;
      /** 被中继的原始事件；其 step.id 已加 `{childRunId}:` 前缀避免与父撞车 */
      event: AgentEvent;
    };

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
