/**
 * 聊天状态 — Rust pipe 事件驱动（状态挂在 Provider，避免子组件 remount 丢消息）。
 */

import { copilotRunAbort, copilotRunStart } from "@desk/platform";
import { listenCopilotAgui, type CopilotAguiEvent } from "@desk/platform/events";
import { logWrite } from "@desk/platform/ipc/log";
import type { AgentThought } from "@desk/ui";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import type { ChatContext } from "./provider";
import { tryNotifyPriceCompareStarted } from "./run-nav";

export interface ChatToolCall {
  id: string;
  name: string;
  args: string;
  result?: string;
  status: "running" | "done";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  reasoningStreaming?: boolean;
  tools?: ChatToolCall[];
  runThoughts?: AgentThought[];
  streaming?: boolean;
}

export interface ChatStore {
  messages: ChatMessage[];
  send: (text: string) => void;
  busy: boolean;
  error: string | null;
  reset: () => void;
  syncTaskSession: (
    taskId: string | undefined,
    seed?: { user: string; reply?: string | null; error?: string | null },
  ) => void;
  upsertRunReply: (reply: string | undefined) => void;
  upsertRunThoughts: (thoughts: AgentThought[]) => void;
}

const ChatStoreContext = createContext<ChatStore | null>(null);

function newId(): string {
  return crypto.randomUUID();
}

function emptyAssistantMessage(id: string): ChatMessage {
  return {
    id,
    role: "assistant",
    content: "",
    reasoning: "",
    reasoningStreaming: false,
    tools: [],
    streaming: true,
  };
}

function reportChatError(message: string, context?: { code?: string }): void {
  const parts = [message];
  if (context?.code) {
    parts.push(`(${context.code})`);
  }
  void logWrite(`[copilot:task_copilot] ${parts.join(" ")}`, "ERROR").catch(() => {});
}

function updateAssistant(
  messages: ChatMessage[],
  assistantId: string,
  updater: (message: ChatMessage) => ChatMessage,
): ChatMessage[] {
  return messages.map((item) => (item.id === assistantId ? updater(item) : item));
}

function eventRunId(event: CopilotAguiEvent): string {
  return event.run_id ?? (event as { runId?: string }).runId ?? "";
}

const NEW_SESSION_KEY = "__new__";
const SEED_USER_ID = "seed-user";
const SEED_ASSISTANT_ID = "seed-assistant";

function seedFromRecord(seed: {
  user: string;
  reply?: string | null;
  error?: string | null;
}): ChatMessage[] {
  const user = seed.user.trim();
  if (!user) {
    return [];
  }
  const messages: ChatMessage[] = [
    { id: SEED_USER_ID, role: "user", content: user },
  ];
  const reply = seed.reply?.trim();
  const error = seed.error?.trim();
  const assistantBody = reply || (error ? `任务失败：${error}` : "");
  if (assistantBody) {
    messages.push({
      id: SEED_ASSISTANT_ID,
      role: "assistant",
      content: assistantBody,
      streaming: false,
    });
  }
  return messages;
}

/** Provider 内部：创建聊天 store。 */
export function useChatStore(ready: boolean, getContext: () => ChatContext): ChatStore {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const threadIdRef = useRef(newId());
  const activeRunIdRef = useRef<string | null>(null);
  const toolNamesRef = useRef(new Map<string, string>());
  const messagesRef = useRef(messages);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  const sessionKeyRef = useRef(NEW_SESSION_KEY);
  const sessionsRef = useRef(new Map<string, ChatMessage[]>());

  useEffect(() => {
    sessionsRef.current.set(sessionKeyRef.current, messages);
  }, [messages]);

  const persistCurrentSession = useCallback(() => {
    sessionsRef.current.set(sessionKeyRef.current, messagesRef.current);
  }, []);

  const abortActive = useCallback(() => {
    const runId = activeRunIdRef.current;
    if (runId) {
      activeRunIdRef.current = null;
      void copilotRunAbort(runId).catch(() => {});
    }
  }, []);

  const syncTaskSession = useCallback(
    (
      taskId: string | undefined,
      seed?: { user: string; reply?: string | null; error?: string | null },
    ) => {
      const nextKey = taskId ?? NEW_SESSION_KEY;
      const prevKey = sessionKeyRef.current;

      if (prevKey === nextKey) {
        if (messagesRef.current.length === 0 && seed?.user) {
          const seeded = seedFromRecord(seed);
          setMessages(seeded);
          sessionsRef.current.set(nextKey, seeded);
        }
        return;
      }

      persistCurrentSession();
      sessionKeyRef.current = nextKey;
      abortActive();
      setBusy(false);
      setError(null);
      toolNamesRef.current.clear();
      threadIdRef.current = newId();

      const migratingFromNew = prevKey === NEW_SESSION_KEY && nextKey !== NEW_SESSION_KEY;
      const current = messagesRef.current;
      if (migratingFromNew && current.length > 0) {
        setMessages(current);
        sessionsRef.current.set(nextKey, current);
        return;
      }

      const saved = sessionsRef.current.get(nextKey);
      if (saved && saved.length > 0) {
        setMessages(saved);
        return;
      }

      if (seed?.user) {
        const seeded = seedFromRecord(seed);
        setMessages(seeded);
        sessionsRef.current.set(nextKey, seeded);
        return;
      }

      setMessages([]);
    },
    [abortActive, persistCurrentSession],
  );

  const upsertRunReply = useCallback((reply: string | undefined) => {
    const trimmed = reply?.trim();
    if (!trimmed) {
      return;
    }
    setMessages((prev) => {
      const seedIdx = prev.findIndex((item) => item.id === SEED_ASSISTANT_ID);
      if (seedIdx >= 0) {
        if (prev[seedIdx]?.content === trimmed) {
          return prev;
        }
        const next = [...prev];
        next[seedIdx] = { ...next[seedIdx]!, content: trimmed, streaming: false };
        return next;
      }
      const hasUser = prev.some((item) => item.id === SEED_USER_ID);
      if (hasUser) {
        return [
          ...prev,
          {
            id: SEED_ASSISTANT_ID,
            role: "assistant",
            content: trimmed,
            streaming: false,
          },
        ];
      }
      return prev;
    });
  }, []);

  const upsertRunThoughts = useCallback((thoughts: AgentThought[]) => {
    if (thoughts.length === 0) {
      return;
    }
    const running = thoughts.some((item) => item.status === "running");
    setMessages((prev) => {
      const apply = (message: ChatMessage): ChatMessage => ({
        ...message,
        runThoughts: thoughts,
        streaming: running && !message.content ? true : message.content ? false : message.streaming,
      });

      const seedIdx = prev.findIndex((item) => item.id === SEED_ASSISTANT_ID);
      if (seedIdx >= 0) {
        return prev.map((item, index) => (index === seedIdx ? apply(item) : item));
      }

      const lastAssistantIdx = prev.reduce<number>(
        (found, item, index) => (item.role === "assistant" ? index : found),
        -1,
      );
      if (lastAssistantIdx >= 0) {
        return prev.map((item, index) => (index === lastAssistantIdx ? apply(item) : item));
      }

      const hasUser = prev.some((item) => item.role === "user");
      if (!hasUser) {
        return prev;
      }

      return [
        ...prev,
        {
          id: SEED_ASSISTANT_ID,
          role: "assistant",
          content: "",
          streaming: running,
          runThoughts: thoughts,
        },
      ];
    });
  }, []);

  const reset = useCallback(() => {
    abortActive();
    threadIdRef.current = newId();
    sessionKeyRef.current = NEW_SESSION_KEY;
    sessionsRef.current.delete(NEW_SESSION_KEY);
    setMessages([]);
    setError(null);
    setBusy(false);
    toolNamesRef.current.clear();
  }, [abortActive]);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!ready || !trimmed || busy) {
        return;
      }

      abortActive();
      toolNamesRef.current.clear();

      const userMessage: ChatMessage = {
        id: newId(),
        role: "user",
        content: trimmed,
      };
      const assistantId = newId();
      const history = [...messagesRef.current, userMessage];

      setMessages([...history, emptyAssistantMessage(assistantId)]);
      setBusy(true);
      setError(null);

      const runId = newId();
      activeRunIdRef.current = runId;

      let unlisten: (() => void) | null = null;

      const finish = () => {
        if (unlisten) {
          unlisten();
          unlisten = null;
        }
        if (activeRunIdRef.current === runId) {
          activeRunIdRef.current = null;
        }
        setBusy(false);
      };

      const handleEvent = (event: CopilotAguiEvent) => {
        if (eventRunId(event) !== runId) {
          return;
        }

        if (event.type === "REASONING_MESSAGE_START") {
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => ({
              ...item,
              reasoningStreaming: true,
            })),
          );
        }

        if (event.type === "REASONING_MESSAGE_CONTENT" && event.delta) {
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => ({
              ...item,
              reasoning: `${item.reasoning ?? ""}${event.delta}`,
              reasoningStreaming: true,
            })),
          );
        }

        if (event.type === "REASONING_MESSAGE_END") {
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => ({
              ...item,
              reasoningStreaming: false,
            })),
          );
        }

        if (event.type === "TEXT_MESSAGE_CONTENT" && event.delta) {
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => ({
              ...item,
              content: item.content + event.delta!,
            })),
          );
        }

        if (event.type === "TOOL_CALL_START" && event.tool_call_id && event.tool_name) {
          toolNamesRef.current.set(event.tool_call_id, event.tool_name);
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => {
              const tools = item.tools ?? [];
              if (tools.some((tool) => tool.id === event.tool_call_id)) {
                return item;
              }
              return {
                ...item,
                tools: [
                  ...tools,
                  {
                    id: event.tool_call_id!,
                    name: event.tool_name!,
                    args: "",
                    status: "running",
                  },
                ],
              };
            }),
          );
        }

        if (event.type === "TOOL_CALL_ARGS" && event.tool_call_id && event.args_delta) {
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => ({
              ...item,
              tools: (item.tools ?? []).map((tool) =>
                tool.id === event.tool_call_id
                  ? { ...tool, args: tool.args + event.args_delta! }
                  : tool,
              ),
            })),
          );
        }

        if (event.type === "TOOL_CALL_RESULT" && event.tool_call_id) {
          tryNotifyPriceCompareStarted(
            toolNamesRef.current.get(event.tool_call_id),
            event.content,
          );
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => ({
              ...item,
              tools: (item.tools ?? []).map((tool) =>
                tool.id === event.tool_call_id
                  ? {
                      ...tool,
                      result: event.content,
                      status: "done" as const,
                    }
                  : tool,
              ),
            })),
          );
        }

        if (event.type === "RUN_ERROR") {
          const detail = event.message ?? "副驾运行失败";
          reportChatError(detail, { code: event.code });
          setError(detail);
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => ({
              ...item,
              content: item.content || detail,
              streaming: false,
              reasoningStreaming: false,
            })),
          );
          finish();
        }

        if (event.type === "RUN_FINISHED") {
          setMessages((prev) =>
            updateAssistant(prev, assistantId, (item) => ({
              ...item,
              streaming: false,
              reasoningStreaming: false,
              tools: (item.tools ?? []).map((tool) =>
                tool.status === "running" ? { ...tool, status: "done" as const } : tool,
              ),
            })),
          );
          finish();
        }
      };

      void listenCopilotAgui(handleEvent).then((fn) => {
        unlisten = fn;
      });

      const context = getContext();
      void copilotRunStart({
        threadId: threadIdRef.current,
        runId,
        messages: history.map((item) => ({
          id: item.id,
          role: item.role,
          content: item.content,
        })),
        state: context.state,
      }).catch((reason) => {
        const detail = reason instanceof Error ? reason.message : String(reason);
        reportChatError(detail);
        setError(detail);
        setMessages((prev) =>
          updateAssistant(prev, assistantId, (item) => ({
            ...item,
            streaming: false,
            reasoningStreaming: false,
          })),
        );
        finish();
      });
    },
    [abortActive, busy, getContext, ready],
  );

  return { messages, send, busy, error, reset, syncTaskSession, upsertRunReply, upsertRunThoughts };
}

export function useChat(): ChatStore {
  const store = useContext(ChatStoreContext);
  if (!store) {
    throw new Error("useChat must be used within ChatProvider");
  }
  return store;
}

export { ChatStoreContext };
