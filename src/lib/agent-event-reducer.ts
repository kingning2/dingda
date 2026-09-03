import type { AgentEvent } from "@/contracts/agent-event";
import type { AgentWorkDetailView, AgentWorkMessageView, AgentWorkStepView } from "@/contracts/ai-work";

export interface AgentRunMessageState {
  content: string;
  thinking: string;
  steps: AgentWorkStepView[];
  error: string | null;
  completed: boolean;
}

export function createAgentRunMessageState(): AgentRunMessageState {
  return {
    content: "",
    thinking: "",
    steps: [],
    error: null,
    completed: false,
  };
}

const STEP_RUNNING = {
  state: "running",
  label: "执行中",
  hint: null,
  badge_class: "bg-sky-500/15 text-sky-700",
};

const STEP_DONE = {
  state: "ready",
  label: "已完成",
  hint: null,
  badge_class: "bg-emerald-500/15 text-emerald-600",
};

function summarizeToolInput(input: unknown): string | null {
  if (input === null || input === undefined) return null;
  if (typeof input === "string") return input;
  try {
    const text = JSON.stringify(input);
    return text.length > 120 ? `${text.slice(0, 117)}...` : text;
  } catch {
    return null;
  }
}

export function reduceAgentEvent(
  state: AgentRunMessageState,
  event: AgentEvent,
): AgentRunMessageState {
  switch (event.type) {
    case "runStarted":
      return state;
    case "textDelta":
      return { ...state, content: state.content + event.text };
    case "thinking":
      return { ...state, thinking: state.thinking + event.text };
    case "toolCall": {
      const hint = summarizeToolInput(event.input);
      const step: AgentWorkStepView = {
        id: event.id || `tool-${state.steps.length + 1}`,
        label: event.name,
        hint,
        status: STEP_RUNNING,
      };
      const existing = state.steps.findIndex((item) => item.id === step.id);
      if (existing >= 0) {
        const steps = [...state.steps];
        steps[existing] = { ...steps[existing], label: step.label, hint: step.hint };
        return { ...state, steps };
      }
      return { ...state, steps: [...state.steps, step] };
    }
    case "toolResult": {
      const steps = state.steps.map((step) =>
        step.id === event.id
          ? {
              ...step,
              status: STEP_DONE,
              hint: summarizeToolInput(event.output) ?? step.hint,
            }
          : step,
      );
      return { ...state, steps };
    }
    case "fileChanged":
      return state;
    case "error": {
      const errorLine = `[错误] ${event.message}`;
      return {
        ...state,
        error: event.message,
        content: state.content ? `${state.content}\n\n${errorLine}` : errorLine,
      };
    }
    case "runCompleted":
      return { ...state, completed: true };
    default:
      return state;
  }
}

export function applyRunStateToAssistantMessage(
  message: AgentWorkMessageView,
  state: AgentRunMessageState,
): AgentWorkMessageView {
  return {
    ...message,
    content: state.content,
    thinking: state.thinking || null,
    steps: state.steps.length > 0 ? state.steps : message.steps,
  };
}

export function applyRunStateToDetail(
  detail: AgentWorkDetailView,
  assistantMessageId: string,
  state: AgentRunMessageState,
): AgentWorkDetailView {
  const messages = detail.messages.map((message) =>
    message.id === assistantMessageId
      ? applyRunStateToAssistantMessage(message, state)
      : message,
  );

  const status = state.error
    ? {
        state: "error" as const,
        label: "执行失败",
        hint: state.error,
        badge_class: "bg-red-500/15 text-red-700",
      }
    : state.completed
      ? {
          state: "ready" as const,
          label: "已完成",
          hint: null,
          badge_class: "bg-emerald-500/15 text-emerald-600",
        }
      : detail.status;

  return {
    ...detail,
    messages,
    status,
    can_send: state.completed,
  };
}

export function createOptimisticSendDetail(
  detail: AgentWorkDetailView,
  userText: string,
  agentId: string,
  modelId: string | null | undefined,
): { detail: AgentWorkDetailView; assistantMessageId: string } {
  const now = new Date().toISOString();
  const userMessage: AgentWorkMessageView = {
    id: `${detail.work_id}-user-${Date.now()}`,
    role: "user",
    content: userText,
    created_at: now,
  };
  const assistantMessageId = `${detail.work_id}-assistant-${Date.now()}`;
  const assistantMessage: AgentWorkMessageView = {
    id: assistantMessageId,
    role: "assistant",
    content: "",
    thinking: "",
    created_at: now,
    steps: [],
  };

  return {
    assistantMessageId,
    detail: {
      ...detail,
      can_send: false,
      composer_agent_id: agentId,
      composer_model_id: modelId ?? null,
      status: {
        state: "running",
        label: "执行中",
        hint: "Agent CLI 正在处理请求…",
        badge_class: "bg-sky-500/15 text-sky-700",
      },
      messages: [...detail.messages, userMessage, assistantMessage],
    },
  };
}
