/**
 * AI 工作详情状态：加载、自动发送 draft、接回在跑的 run、持久化、发送/重发/取消。
 *
 * 职责：
 *   - 从 SQLite 加载工作详情，并探一次「服务端还有没有 run 在跑」。
 *   - 若存在草稿（首页提交后暂存），自动发送；若服务端还在跑，接回去看直播。
 *   - 运行时状态更新（SSE 事件折叠后的 detail + phase）。
 *   - 持久化：debounce 写回 SQLite，页面卸载时 flush。
 *   - 发送/重发/取消编排。
 *
 * 设计说明：
 *   - `applyRef` 解决 effect stale closure：加载 effect 里用 `applyRef.current`
 *     而不是闭包捕获的 `applyDetailUpdate`，确保 generation 校验后用的是最新回调。
 *   - `autoRunByWork` / `mountCountByWork` 是模块级 Map，跨实例共享：
 *     前者防止 StrictMode 双 mount 把同一轮跑两遍，后者区分「真的离开了页面」
 *     与「只是 StrictMode 的卸载/重挂」。
 *   - 离开页面只 `detach`（不叫停）：run 的生命周期归服务端，重进这个 work
 *     会重新探针并接回来。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentRunPhase } from "@v2/ui-agent/run/phase";
import { putAgentWorkDetail } from "@v2/ui-agent/api";
import type { AgentWorkDetailView } from "@v2/contracts/ai-work";
import type { ComposerSubmitPayload } from "@v2/contracts/composer";
import { truncateBeforeUserMessage } from "@v2/ui-agent/run/reducer";
import { clearWorkDraft, loadAgentWorkDetail, stashWorkSnapshot } from "../work/session";
import { attach, send, type SendHandle } from "../work/send";

const PERSIST_DEBOUNCE_MS = 800;

/** 这个 work 当前在跟随的那一轮运行；防止 StrictMode 双 mount 重复起手。 */
const autoRunByWork = new Map<string, SendHandle>();
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

  // 加载详情 + 起手这一轮（发首条草稿 / 接回服务端还在跑的 run）
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

        const onUpdate = (next: AgentWorkDetailView, nextPhase: AgentRunPhase) => {
          if (generation !== loadGenerationRef.current) return;
          applyRef.current(next, { runPhase: nextPhase });
        };

        /**
         * 两条起手路径，都不走就只是看历史。
         *
         * 草稿优先：它意味着这一轮还没发出去，而探针命中的是上一轮 —— 但两者
         * 不会同时出现（草稿只在页面上没有任何消息时存在，那种 work 不会有在跑的 run）。
         */
        const startRun = (): SendHandle | null => {
          const draft = result.pendingSend;
          if (draft) {
            clearWorkDraft(workId);
            return send(result.detail, draft, onUpdate);
          }
          const activeRunId = result.activeRunId;
          return activeRunId ? attach(result.detail, activeRunId, onUpdate) : null;
        };

        let handle = autoRunByWork.get(workId) ?? startRun();
        if (!handle) return;
        if (!autoRunByWork.has(workId)) {
          autoRunByWork.set(workId, handle);
          void handle.promise.finally(() => {
            if (autoRunByWork.get(workId) === handle) {
              autoRunByWork.delete(workId);
            }
          });
        }
        activeSendRef.current = handle;
        try {
          await handle.promise;
        } catch (err) {
          if (!cancelled && generation === loadGenerationRef.current) {
            setError(err instanceof Error ? err.message : "执行失败，请重试");
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
      const handle = autoRunByWork.get(workId) ?? activeSendRef.current;
      const nextCount = (mountCountByWork.get(workId) ?? 1) - 1;
      if (nextCount <= 0) mountCountByWork.delete(workId);
      else mountCountByWork.set(workId, nextCount);

      queueMicrotask(() => {
        if ((mountCountByWork.get(workId) ?? 0) > 0) return;
        // run 的生命周期归服务端：离开页面只停止跟随，不叫停 —— 重进能接回来。
        // 登记表也清掉，否则下次进这个 work 会复用一个已经停掉的句柄。
        if (autoRunByWork.get(workId) === handle) {
          autoRunByWork.delete(workId);
        }
        if (activeSendRef.current === handle) {
          activeSendRef.current = null;
        }
        handle?.detach();
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
      applyDetailUpdate({
        ...current,
        composer_agent_id: agentId,
        composer_model_id: modelId,
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
