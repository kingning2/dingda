/**
 * 聊天 Provider — sidecar 就绪检测 + 任务上下文注入 + 聊天状态。
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { copilotReady } from "@desk/platform";
import { listenSidecarRestarted } from "@desk/platform/events";

import { ChatStoreContext, useChatStore } from "./use-chat";

export interface ChatContext {
  state?: Record<string, unknown>;
}

type SetChatContext = (context: ChatContext) => void;

const ChatContextSetterContext = createContext<SetChatContext>(() => {});
const ChatReadyContext = createContext(false);
const ChatUnavailableContext = createContext(false);
const ChatContextRefContext = createContext<() => ChatContext>(() => ({}));

const ChatSessionContext = createContext<(() => void) | null>(null);

/** 注入任务上下文快照（任务列表 / 当前 run 详情）。 */
export function useTaskContext(state?: Record<string, unknown>): void {
  const setContext = useContext(ChatContextSetterContext);
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
    setContext({ state: stateRef.current });
  }, [setContext, state]);
}

export function useChatReady(): boolean {
  return useContext(ChatReadyContext);
}

export function useChatUnavailable(): boolean {
  return useContext(ChatUnavailableContext);
}

export function useChatContextRef(): () => ChatContext {
  return useContext(ChatContextRefContext);
}

/** 新对话：清空消息与 thread（不 remount 子树）。 */
export function useStartNewChat(): () => void {
  const startNewChat = useContext(ChatSessionContext);
  if (!startNewChat) {
    throw new Error("useStartNewChat must be used within ChatProvider");
  }
  return startNewChat;
}

const READY_MAX_ATTEMPTS = 30;
const READY_RETRY_MS = 1_000;

export function ChatProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [discoveryKey, setDiscoveryKey] = useState(0);
  const contextRef = useRef<ChatContext>({});

  const setContext = useMemo<SetChatContext>(() => (context) => {
    contextRef.current = { ...contextRef.current, ...context };
  }, []);

  const getContext = useMemo(() => () => contextRef.current, []);
  const chat = useChatStore(ready, getContext);
  const resetRef = useRef(chat.reset);

  useEffect(() => {
    resetRef.current = chat.reset;
  }, [chat.reset]);

  const startNewChat = useCallback(() => {
    resetRef.current();
  }, []);

  useEffect(() => {
    let cancelled = false;
    let attempt = 0;

    const discover = () => {
      if (cancelled) {
        return;
      }
      void copilotReady()
        .then((isReady) => {
          if (cancelled) {
            return;
          }
          if (isReady) {
            setUnavailable(false);
            setReady(true);
            return;
          }
          attempt += 1;
          if (attempt >= READY_MAX_ATTEMPTS) {
            setUnavailable(true);
            return;
          }
          window.setTimeout(discover, READY_RETRY_MS);
        })
        .catch(() => {
          if (!cancelled) {
            attempt += 1;
            if (attempt >= READY_MAX_ATTEMPTS) {
              setUnavailable(true);
            } else {
              window.setTimeout(discover, READY_RETRY_MS);
            }
          }
        });
    };

    discover();
    return () => {
      cancelled = true;
    };
  }, [discoveryKey]);

  useEffect(() => {
    let cancelled = false;
    void listenSidecarRestarted(() => {
      if (cancelled) {
        return;
      }
      setReady(false);
      setUnavailable(false);
      setDiscoveryKey((key) => key + 1);
    }).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <ChatContextSetterContext.Provider value={setContext}>
      <ChatReadyContext.Provider value={ready}>
        <ChatUnavailableContext.Provider value={unavailable}>
          <ChatSessionContext.Provider value={startNewChat}>
            <ChatContextRefContext.Provider value={getContext}>
              <ChatStoreContext.Provider value={chat}>{children}</ChatStoreContext.Provider>
            </ChatContextRefContext.Provider>
          </ChatSessionContext.Provider>
        </ChatUnavailableContext.Provider>
      </ChatReadyContext.Provider>
    </ChatContextSetterContext.Provider>
  );
}
