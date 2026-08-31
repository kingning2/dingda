import { createDeskStore } from "@desk/store";

import { SEED_CONVERSATIONS } from "./mock-data";
import type {
  AgentEvent,
  AgentMessage,
  AgentRunState,
  Conversation,
} from "./types";

function newId(): string {
  return crypto.randomUUID();
}

function emptyRun(conversationId: string, runId: string): AgentRunState {
  return {
    id: runId,
    conversationId,
    status: "idle",
    progress: 0,
    messages: [],
    steps: [],
    toolCalls: [],
    products: [],
    analysis: null,
  };
}

export interface AgentStoreState {
  conversations: Conversation[];
  activeConversationId: string | null;
  runs: Record<string, AgentRunState>;
  selectedProductId: string | null;

  createConversation: () => string;
  setActiveConversation: (id: string) => void;
  sendUserMessage: (content: string) => string | null;
  stopRun: () => void;
  applyEvent: (event: AgentEvent) => void;
  setSelectedProduct: (id: string | null) => void;

  activeConversation: () => Conversation | null;
  activeRun: () => AgentRunState | null;
}

export const agentStore = createDeskStore<AgentStoreState>((set, get) => ({
  conversations: [...SEED_CONVERSATIONS],
  activeConversationId: null,
  runs: {},
  selectedProductId: null,

  createConversation: () => {
    const id = newId();
    const conversation: Conversation = {
      id,
      title: "新会话",
      updatedAt: Date.now(),
      status: "idle",
      progress: 0,
      unread: false,
    };
    set((state) => ({
      conversations: [conversation, ...state.conversations],
      activeConversationId: id,
      runs: { ...state.runs, [id]: emptyRun(id, newId()) },
    }));
    return id;
  },

  setActiveConversation: (id) => {
    set((state) => ({
      activeConversationId: id,
      conversations: state.conversations.map((item) =>
        item.id === id ? { ...item, unread: false } : item,
      ),
      runs: state.runs[id]
        ? state.runs
        : { ...state.runs, [id]: emptyRun(id, newId()) },
    }));
  },

  sendUserMessage: (content) => {
    const trimmed = content.trim();
    if (!trimmed) {
      return null;
    }
    const state = get();
    let conversationId = state.activeConversationId;
    if (!conversationId) {
      conversationId = get().createConversation();
    }

    const runId = newId();
    const userMessage: AgentMessage = {
      id: newId(),
      role: "user",
      content: trimmed,
      createdAt: Date.now(),
    };

    set((s) => ({
      conversations: s.conversations.map((item) =>
        item.id === conversationId
          ? {
              ...item,
              title: item.title === "新会话" ? trimmed.slice(0, 32) : item.title,
              updatedAt: Date.now(),
              status: "running" as const,
              progress: 0,
            }
          : item,
      ),
      runs: {
        ...s.runs,
        [conversationId!]: {
          id: runId,
          conversationId: conversationId!,
          status: "running",
          progress: 0,
          messages: [userMessage],
          steps: [],
          toolCalls: [],
          products: [],
          analysis: null,
        },
      },
    }));

    return runId;
  },

  stopRun: () => {
    const run = get().activeRun();
    if (!run || run.status !== "running") {
      return;
    }
    get().applyEvent({ type: "run.error", runId: run.id, error: "已停止" });
  },

  applyEvent: (event) => {
    set((state) => {
      const conversationId = state.activeConversationId;
      if (!conversationId) {
        return state;
      }
      const run = Object.values(state.runs).find(
        (item) => item.conversationId === conversationId && item.status === "running",
      ) ?? state.runs[conversationId];
      if (!run) {
        return state;
      }

      let nextRun = { ...run };
      let nextConversations = state.conversations;

      switch (event.type) {
        case "run.started":
          nextRun = { ...nextRun, id: event.runId, status: "running", progress: 0 };
          break;
        case "message.delta": {
          const last = nextRun.messages[nextRun.messages.length - 1];
          if (last?.role === "assistant") {
            nextRun = {
              ...nextRun,
              messages: nextRun.messages.map((item, index) =>
                index === nextRun.messages.length - 1
                  ? { ...item, content: item.content + event.content }
                  : item,
              ),
            };
          } else {
            nextRun = {
              ...nextRun,
              messages: [
                ...nextRun.messages,
                {
                  id: newId(),
                  role: "assistant",
                  content: event.content,
                  createdAt: Date.now(),
                },
              ],
            };
          }
          break;
        }
        case "step.started":
          nextRun = {
            ...nextRun,
            steps: [...nextRun.steps, event.step],
          };
          break;
        case "step.updated":
          nextRun = {
            ...nextRun,
            steps: nextRun.steps.map((step) =>
              step.id === event.stepId ? { ...step, ...event.data } : step,
            ),
          };
          break;
        case "tool.started":
          nextRun = {
            ...nextRun,
            toolCalls: [...nextRun.toolCalls, event.tool],
          };
          break;
        case "tool.finished":
          nextRun = {
            ...nextRun,
            toolCalls: nextRun.toolCalls.map((tool) =>
              tool.id === event.toolId
                ? {
                    ...tool,
                    status: event.error ? "error" : "success",
                    result: event.result,
                    error: event.error,
                    finishedAt: Date.now(),
                    duration: Date.now() - tool.startedAt,
                  }
                : tool,
            ),
          };
          break;
        case "product.found":
          if (!nextRun.products.some((item) => item.id === event.product.id)) {
            nextRun = {
              ...nextRun,
              products: [...nextRun.products, event.product],
            };
          }
          break;
        case "progress.updated":
          nextRun = {
            ...nextRun,
            progress: event.progress,
            progressMessage: event.message,
          };
          nextConversations = state.conversations.map((item) =>
            item.id === conversationId
              ? { ...item, progress: event.progress, updatedAt: Date.now() }
              : item,
          );
          break;
        case "analysis.updated":
          nextRun = {
            ...nextRun,
            analysis: {
              summary: [],
              priceBuckets: [],
              distribution: [],
              ...nextRun.analysis,
              ...event.data,
            },
          };
          break;
        case "run.finished":
          nextRun = { ...nextRun, status: "completed", progress: 100 };
          nextConversations = state.conversations.map((item) =>
            item.id === conversationId
              ? { ...item, status: "completed", progress: 100, updatedAt: Date.now() }
              : item,
          );
          break;
        case "run.error":
          nextRun = { ...nextRun, status: "error", error: event.error };
          nextConversations = state.conversations.map((item) =>
            item.id === conversationId
              ? { ...item, status: "error", updatedAt: Date.now() }
              : item,
          );
          break;
        default:
          break;
      }

      return {
        ...state,
        conversations: nextConversations,
        runs: { ...state.runs, [conversationId]: nextRun },
      };
    });
  },

  setSelectedProduct: (id) => set({ selectedProductId: id }),

  activeConversation: () => {
    const { conversations, activeConversationId } = get();
    return conversations.find((item) => item.id === activeConversationId) ?? null;
  },

  activeRun: () => {
    const { runs, activeConversationId } = get();
    if (!activeConversationId) {
      return null;
    }
    return runs[activeConversationId] ?? null;
  },
}));

export const useAgentStore = agentStore;
