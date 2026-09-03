import type { ComposerSubmitPayload } from "@/contracts/composer";
import type { AgentWorkDetailView } from "@/contracts/ai-work";
import {
  applyRunStateToDetail,
  createAgentRunMessageState,
  createOptimisticSendDetail,
  reduceAgentEvent,
} from "@/lib/agent-event-reducer";
import { runAgentWithEvents } from "@/lib/agent-run";

export async function sendAgentWorkViaCli(
  detail: AgentWorkDetailView,
  payload: ComposerSubmitPayload,
  onUpdate: (next: AgentWorkDetailView) => void,
): Promise<AgentWorkDetailView> {
  const message = payload.message.trim();
  if (!message) return detail;

  const { detail: optimistic, assistantMessageId } = createOptimisticSendDetail(
    detail,
    message,
    payload.agent_id,
    payload.model_id,
  );
  onUpdate(optimistic);

  let state = createAgentRunMessageState();
  let snapshot = optimistic;

  const flush = () => {
    snapshot = applyRunStateToDetail(snapshot, assistantMessageId, state);
    onUpdate(snapshot);
  };

  try {
    await runAgentWithEvents(
      {
        runtimeId: payload.agent_id,
        prompt: message,
        modelId: payload.model_id ?? null,
      },
      (event) => {
        state = reduceAgentEvent(state, event);
        flush();
      },
    );
  } catch (error) {
    const messageText =
      error instanceof Error ? error.message : "Agent CLI 启动或执行失败";
    state = reduceAgentEvent(state, { type: "error", message: messageText });
    state = { ...state, completed: true };
    flush();
    throw error;
  }

  flush();
  return snapshot;
}
