/** 统一 Agent 事件 — 与 Rust `AgentEvent` + `AgentEventEnvelope` 对齐。 */

export type AgentEvent =
  | { type: "runStarted"; runtimeId: string; runId: string }
  | { type: "textDelta"; text: string }
  | { type: "thinking"; text: string }
  | { type: "toolCall"; id: string; name: string; input: unknown }
  | { type: "toolResult"; id: string; output: unknown }
  | { type: "fileChanged"; path: string }
  | { type: "error"; message: string }
  | { type: "runCompleted"; exitCode: number };

/** Tauri `agent-event` 推送信封（`runId` + 扁平化 event 字段）。 */
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
