/**
 * 比价 Agent run — 启动 / 轮询 / 事件合并 / 暂停继续取消 / 历史会话恢复。
 *
 * 交互形态对齐 DeepSeek Harness：composer 提交后靠步骤事件驱动转录区。
 * 会话落在 Rust `agent-runs.json`，页面挂载时恢复最近一次 price_compare。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { listenAgentProgress } from "@desk/platform/events";
import {
  agentRunCancel,
  agentRunList,
  agentRunPause,
  agentRunResume,
  agentRunStart,
  agentRunStatus,
  type AgentRunRecord,
} from "@desk/platform/ipc/agent-run";

/** 运行中（含暂停、等网）视为会话未结束。 */
const ACTIVE_STATES = new Set(["running", "paused", "waiting_network"]);
/** 冷启动后孤儿 / 失败：可从断点重新拉起。 */
const RESUME_FROM_STORE = new Set(["interrupted", "failed", "cancelled"]);

export interface PriceCompareSession {
  /** 用户本轮输入。 */
  prompt: string;
  /** 当前或最近一次 run。 */
  run: AgentRunRecord | null;
}

export interface UsePriceCompareRunResult {
  draft: string;
  setDraft: (value: string) => void;
  session: PriceCompareSession | null;
  /** 历史恢复完成前为 false，避免空态闪烁。 */
  ready: boolean;
  busy: boolean;
  error: string | null;
  start: () => Promise<void>;
  pause: () => Promise<void>;
  resume: () => Promise<void>;
  cancel: () => Promise<void>;
  clear: () => void;
}

function toError(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

/**
 * 管理一次比价对话会话。
 */
export function usePriceCompareRun(): UsePriceCompareRunResult {
  const [draft, setDraft] = useState("");
  const [session, setSession] = useState<PriceCompareSession | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const runIdRef = useRef<string | null>(null);

  const mergeRun = useCallback((run: AgentRunRecord) => {
    setSession((current) => {
      if (!current) {
        return { prompt: run.user, run };
      }
      return { ...current, prompt: current.prompt || run.user, run };
    });
    runIdRef.current = run.id;
    setBusy(ACTIVE_STATES.has(run.state));
  }, []);

  const refresh = useCallback(
    async (runId: string) => {
      try {
        const run = await agentRunStatus(runId);
        mergeRun(run);
      } catch {
        /* 轮询失败忽略，下一拍再试 */
      }
    },
    [mergeRun],
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const runs = await agentRunList();
        if (cancelled) {
          return;
        }
        const latest = runs.find((run) => run.kind === "price_compare");
        if (latest) {
          mergeRun(latest);
        }
      } catch {
        /* 无历史或 IPC 未就绪时保持空态 */
      } finally {
        if (!cancelled) {
          setReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mergeRun]);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;
    void listenAgentProgress((payload) => {
      if (cancelled) {
        return;
      }
      const activeId = runIdRef.current;
      if (!activeId || payload.runId !== activeId) {
        return;
      }
      void refresh(activeId);
    }).then((dispose) => {
      if (cancelled) {
        dispose();
        return;
      }
      unlisten = dispose;
    });
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [refresh]);

  useEffect(() => {
    const runId = session?.run?.id;
    const state = session?.run?.state;
    if (!runId || !state || !ACTIVE_STATES.has(state)) {
      return;
    }
    const timer = window.setInterval(() => {
      void refresh(runId);
    }, 800);
    return () => window.clearInterval(timer);
  }, [session?.run?.id, session?.run?.state, refresh]);

  const start = useCallback(async () => {
    const prompt = draft.trim();
    if (!prompt || busy) {
      return;
    }
    setError(null);
    setBusy(true);
    setSession({ prompt, run: null });
    try {
      const run = await agentRunStart({ user: prompt });
      setDraft("");
      mergeRun(run);
    } catch (cause) {
      setError(toError(cause));
      setBusy(false);
      setSession(null);
    }
  }, [draft, busy, mergeRun]);

  const pause = useCallback(async () => {
    const runId = runIdRef.current;
    if (!runId) {
      return;
    }
    setError(null);
    try {
      mergeRun(await agentRunPause(runId));
    } catch (cause) {
      setError(toError(cause));
    }
  }, [mergeRun]);

  const resume = useCallback(async () => {
    const current = session?.run;
    const runId = current?.id ?? runIdRef.current;
    if (!runId || !current) {
      return;
    }
    setError(null);
    setBusy(true);
    try {
      if (RESUME_FROM_STORE.has(current.state)) {
        // 冷启动后 Python registry 已空：用持久化步骤从断点重新拉起。
        const run = await agentRunStart({
          user: current.user,
          resumeFromRunId: current.id,
          resumeNode: current.failedNode,
        });
        mergeRun(run);
        return;
      }
      mergeRun(await agentRunResume({ runId, mode: "continue" }));
    } catch (cause) {
      setError(toError(cause));
      setBusy(false);
    }
  }, [mergeRun, session?.run]);

  const cancel = useCallback(async () => {
    const runId = runIdRef.current;
    if (!runId) {
      return;
    }
    setError(null);
    try {
      mergeRun(await agentRunCancel(runId));
    } catch (cause) {
      setError(toError(cause));
    }
  }, [mergeRun]);

  const clear = useCallback(() => {
    if (busy) {
      return;
    }
    runIdRef.current = null;
    setSession(null);
    setError(null);
  }, [busy]);

  return {
    draft,
    setDraft,
    session,
    ready,
    busy,
    error,
    start,
    pause,
    resume,
    cancel,
    clear,
  };
}
