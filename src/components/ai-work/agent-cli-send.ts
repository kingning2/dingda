import type { ComposerSubmitPayload } from "@/contracts/composer";
import type { AgentWorkDetailView } from "@/contracts/ai-work";
import {
  applyRunStateToDetail,
  createAgentRunMessageState,
  createOptimisticSendDetail,
  reduceAgentEvent,
} from "@/lib/agent-event-reducer";
import { runAgentWithEvents } from "@/lib/agent-run";

/** 同 runtime 才续聊；换 Agent 清空 session。 */
function resolveCliSession(
  detail: AgentWorkDetailView,
  agentId: string,
): { sessionId: string | null; runtimeId: string | null } {
  const runtimeId = detail.cli_session_runtime_id ?? null;
  const sessionId = detail.cli_session_id?.trim() || null;
  if (!sessionId || !runtimeId || runtimeId !== agentId) {
    return { sessionId: null, runtimeId: null };
  }
  return { sessionId, runtimeId };
}

export async function sendAgentWorkViaCli(
  detail: AgentWorkDetailView,
  payload: ComposerSubmitPayload,
  onUpdate: (next: AgentWorkDetailView) => void,
): Promise<AgentWorkDetailView> {
  const message = payload.message.trim();
  if (!message) return detail;

  const { sessionId: resumeSessionId } = resolveCliSession(detail, payload.agent_id);
  const { detail: optimistic, assistantMessageId } = createOptimisticSendDetail(
    detail,
    message,
    payload.agent_id,
    payload.model_id,
  );

  // 换 Agent 时清掉旧 session，避免串到别的 CLI
  let snapshot: AgentWorkDetailView = {
    ...optimistic,
    cli_session_id: resumeSessionId,
    cli_session_runtime_id: resumeSessionId ? payload.agent_id : null,
  };
  onUpdate(snapshot);

  let state = createAgentRunMessageState();

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
        sessionId: resumeSessionId,
      },
      (event) => {
        if (event.type === "session" && event.sessionId.trim()) {
          snapshot = {
            ...snapshot,
            cli_session_id: event.sessionId.trim(),
            cli_session_runtime_id: payload.agent_id,
          };
          onUpdate(snapshot);
          return;
        }
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
