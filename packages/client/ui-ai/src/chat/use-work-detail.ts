/**
 * AI 工作详情状态：加载、自动发送 draft、持久化、发送/重发/取消。
 *
 * 职责：
 *   - 从 SQLite 加载工作详情。
 *   - 若存在草稿（首页提交后暂存），自动发送。
 *   - 运行时状态更新（SSE 事件折叠后的 detail + phase）。
 *   - 持久化：debounce 写回 SQLite，页面卸载时 flush。
 *   - 发送/重发/取消编排。
 *
 * 设计说明：
 *   - `applyRef` 解决 effect stale closure：加载 effect 里用 `applyRef.current`
 *     而不是闭包捕获的 `applyDetailUpdate`，确保 generation 校验后用的是最新回调。
 *   - `autoSendByWork` / `mountCountByWork` 是模块级 Map，跨实例共享，
 *     用于防止 StrictMode 双 mount 导致重复发送。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentRunPhase } from "@v2/ui-agent/run/phase";
import { putAgentWorkDetail } from "@v2/ui-agent/api";
import type { AgentWorkDetailView } from "@v2/contracts/ai-work";
import type { ComposerSubmitPayload } from "@v2/contracts/composer";
import { truncateBeforeUserMessage } from "@v2/ui-agent/run/reducer";
import { clearWorkDraft, loadAgentWorkDetail, stashWorkSnapshot } from "../work/session";
import { send, type SendHandle } from "../work/send";

const PERSIST_DEBOUNCE_MS = 800;

/** 防止 StrictMode 双 mount 重复发送。 */
const autoSendByWork = new Map<string, SendHandle>();
const mountCountByWork = new Map<string, number>();

export interface WorkDetailState {
  detail: AgentWorkDetailView | null;
  loading: boolean;
  error: string | null;
  runPhase: AgentRunPhase | null;
  activeSendRef: React.MutableRefObject<SendHandle | null>;
  applyDetailUpdate: (
    next: AgentWorkDetailView,
    options?: { hydrate?: boolean; runPhase?: AgentRunPhase | null },
  ) => void;
  handleSend: (payload: ComposerSubmitPayload) => Promise<void>;
  handleResubmitUser: (messageId: string, content: string) => Promise<void>;
  handleCancel: () => void;
  handleSettingsChange: (agentId: string, modelId: string | null) => void;
}

export function useWorkDetail(workId: string, serverReady: boolean): WorkDetailState {
  const [detail, setDetail] = useState<AgentWorkDetailView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runPhase, setRunPhase] = useState<AgentRunPhase | null>(null);
  const detailRef = useRef<AgentWorkDetailView | null>(null);
  const persistTimerRef = useRef<number | null>(null);
  const loadGenerationRef = useRef(0);
  const activeSendRef = useRef<SendHandle | null>(null);
  const applyRef = useRef<
    (next: AgentWorkDetailView, options?: { hydrate?: boolean; runPhase?: AgentRunPhase | null }) => void
  >(() => undefined);

  const schedulePersist = useCallback((_next: AgentWorkDetailView) => {
    if (persistTimerRef.current !== null) {
      window.clearTimeout(persistTimerRef.current);
    }
    persistTimerRef.current = window.setTimeout(() => {
      persistTimerRef.current = null;
      const snapshot = detailRef.current;
      if (!snapshot) return;
      stashWorkSnapshot(snapshot);
      void putAgentWorkDetail(snapshot).catch(() => {});
    }, PERSIST_DEBOUNCE_MS);
  }, []);

  const flushPersist = useCallback((next?: AgentWorkDetailView | null, keepalive = false) => {
    const snapshot = next ?? detailRef.current;
    if (!snapshot) return;
    if (persistTimerRef.current !== null) {
      window.clearTimeout(persistTimerRef.current);
      persistTimerRef.current = null;
    }
    stashWorkSnapshot(snapshot);
    void putAgentWorkDetail(snapshot, { keepalive }).catch(() => {});
  }, []);

  const applyDetailUpdate = useCallback(
    (
      next: AgentWorkDetailView,
      options?: { hydrate?: boolean; runPhase?: AgentRunPhase | null },
    ) => {
      detailRef.current = next;
      setDetail(next);
      if (options?.runPhase !== undefined) setRunPhase(options.runPhase);
      setLoading(false);
      stashWorkSnapshot(next);
      if (options?.hydrate) return;
      if (next.can_send) {
        flushPersist(next, false);
      } else {
        schedulePersist(next);
      }
    },
    [schedulePersist, flushPersist],
  );
  applyRef.current = applyDetailUpdate;

  // 页面卸载时 flush
  useEffect(() => {
    const onPageHide = () => {
      flushPersist(undefined, true);
    };
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("beforeunload", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("beforeunload", onPageHide);
    };
  }, [flushPersist]);

  // 加载详情 + 自动发送 draft
  useEffect(() => {
    if (!serverReady) return;

    const generation = ++loadGenerationRef.current;
    let cancelled = false;
    mountCountByWork.set(workId, (mountCountByWork.get(workId) ?? 0) + 1);
    setLoading(true);
    setError(null);
    setDetail(null);
    detailRef.current = null;
    setRunPhase(null);

    void loadAgentWorkDetail(workId)
      .then(async (result) => {
        if (cancelled || generation !== loadGenerationRef.current) return;
        applyRef.current(result.detail, { hydrate: true });
        if (!result.pendingSend) return;

        clearWorkDraft(workId);
        let handle = autoSendByWork.get(workId);
        if (!handle) {
          handle = send(result.detail, result.pendingSend, (next, nextPhase) => {
            if (generation !== loadGenerationRef.current) return;
            applyRef.current(next, { runPhase: nextPhase });
          });
          autoSendByWork.set(workId, handle);
          void handle.promise.finally(() => {
            if (autoSendByWork.get(workId) === handle) {
              autoSendByWork.delete(workId);
            }
          });
        }
        activeSendRef.current = handle;
        try {
          await handle.promise;
        } catch (err) {
          if (!cancelled && generation === loadGenerationRef.current) {
            setError(err instanceof Error ? err.message : "发送失败，请重试");
          }
        } finally {
          if (activeSendRef.current === handle) {
            activeSendRef.current = null;
          }
        }
      })
      .catch(() => {
        if (!cancelled && generation === loadGenerationRef.current) {
          setError("加载 AI 工作详情失败");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      const handle = autoSendByWork.get(workId) ?? activeSendRef.current;
      const nextCount = (mountCountByWork.get(workId) ?? 1) - 1;
      if (nextCount <= 0) mountCountByWork.delete(workId);
      else mountCountByWork.set(workId, nextCount);

      queueMicrotask(() => {
        if ((mountCountByWork.get(workId) ?? 0) > 0) return;
        void handle?.cancel();
        if (autoSendByWork.get(workId) === handle) {
          autoSendByWork.delete(workId);
        }
        if (activeSendRef.current === handle) {
          activeSendRef.current = null;
        }
      });
    };
  }, [workId, serverReady]);

  const handleSend = useCallback(
    async (payload: ComposerSubmitPayload) => {
      const current = detailRef.current;
      if (!current || activeSendRef.current) return;
      setError(null);
      const merged: ComposerSubmitPayload = {
        ...payload,
        agent_id: current.composer_agent_id ?? payload.agent_id,
        model_id: current.composer_model_id ?? payload.model_id,
      };
      const handle = send(current, merged, (next, nextPhase) => {
        applyDetailUpdate(next, { runPhase: nextPhase });
      });
      activeSendRef.current = handle;
      try {
        await handle.promise;
      } catch (err) {
        setError(err instanceof Error ? err.message : "发送失败，请重试");
      } finally {
        if (activeSendRef.current === handle) {
          activeSendRef.current = null;
        }
      }
    },
    [applyDetailUpdate],
  );

  const handleResubmitUser = useCallback(
    async (messageId: string, content: string) => {
      const current = detailRef.current;
      if (!current) return;
      const truncated = truncateBeforeUserMessage(current, messageId);
      if (!truncated) return;

      const active = activeSendRef.current;
      if (active) {
        await active.cancel();
        activeSendRef.current = null;
      }

      applyDetailUpdate(truncated);
      setError(null);

      const payload: ComposerSubmitPayload = {
        message: content,
        agent_id: truncated.composer_agent_id ?? "",
        model_id: truncated.composer_model_id,
        attachments: [],
      };
      const handle = send(truncated, payload, (next, nextPhase) => {
        applyDetailUpdate(next, { runPhase: nextPhase });
      });
      activeSendRef.current = handle;
      try {
        await handle.promise;
      } catch (err) {
        setError(err instanceof Error ? err.message : "发送失败，请重试");
      } finally {
        if (activeSendRef.current === handle) {
          activeSendRef.current = null;
        }
      }
    },
    [applyDetailUpdate],
  );

  const handleCancel = useCallback(() => {
    void activeSendRef.current?.cancel();
  }, []);

  const handleSettingsChange = useCallback(
    (agentId: string, modelId: string | null) => {
      const current = detailRef.current;
      if (!current) return;
      const sameRuntime =
        Boolean(current.cli_session_id) &&
        (current.cli_session_runtime_id ?? current.composer_agent_id) === agentId;
      applyDetailUpdate({
        ...current,
        composer_agent_id: agentId,
        composer_model_id: modelId,
        cli_session_id: sameRuntime ? current.cli_session_id : null,
        cli_session_runtime_id: sameRuntime ? agentId : null,
      });
    },
    [applyDetailUpdate],
  );

  return {
    detail,
    loading,
    error,
    runPhase,
    activeSendRef,
    applyDetailUpdate,
    handleSend,
    handleResubmitUser,
    handleCancel,
    handleSettingsChange,
  };
}
