import { useCallback, useRef } from "react";

import type { AgentWorkMessageView } from "@/contracts/ai-work";

/** 记录工作区首次渲染时的消息，避免历史记录也走打字机。 */
export function useMessageTypewriter(workId: string, messages: AgentWorkMessageView[]) {
  const baselineRef = useRef<{ workId: string; ids: Set<string> } | null>(null);
  const completedRef = useRef<Set<string>>(new Set());

  if (!baselineRef.current || baselineRef.current.workId !== workId) {
    baselineRef.current = {
      workId,
      ids: new Set(messages.map((message) => message.id)),
    };
    completedRef.current = new Set();
  }

  const shouldTypewriter = useCallback(
    (message: AgentWorkMessageView) => {
      if (message.role !== "assistant" || !message.content) return false;
      const baseline = baselineRef.current;
      if (!baseline || baseline.workId !== workId) return false;
      if (baseline.ids.has(message.id)) return false;
      if (completedRef.current.has(message.id)) return false;
      return true;
    },
    [workId],
  );

  const markTypewriterComplete = useCallback((messageId: string) => {
    completedRef.current.add(messageId);
  }, []);

  return { shouldTypewriter, markTypewriterComplete };
}
