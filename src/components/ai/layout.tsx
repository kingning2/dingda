/**
 * AI 工作页：唯一 Layout — 左聊天（调度器）/ 右结果|设置。
 */

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowLeft, Loader2, Package, Settings2 } from "lucide-react";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import type { AgentWorkDetailView, AgentWorkStepView } from "@/contracts/ai-work";
import { putAgentWorkDetail } from "@/lib/agent-api";
import { useServer } from "@/providers/server-provider";
import { useComposerAgentOptions } from "@/components/composer/composer-agents";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { clearWorkDraft, loadAgentWorkDetail, stashWorkSnapshot } from "./session";
import { ChatPane, send, type SendHandle } from "./scheduler";
import { Products } from "./Products";
import { ProductPreviewHost } from "./ProductPreviewHost";
import { Settings } from "./Settings";
import { truncateBeforeUserMessage } from "@/lib/agent-event-reducer";

export type SideTab = "results" | "settings";

const MIN_CHAT_WIDTH = 360;
const MAX_CHAT_WIDTH = 720;
const DEFAULT_CHAT_WIDTH = 520;
const PERSIST_DEBOUNCE_MS = 800;

const autoSendByWork = new Map<string, SendHandle>();
const mountCountByWork = new Map<string, number>();

interface LayoutProps {
  workId: string;
  onBack?: () => void;
}

/** AI 工作页入口（对外 AiWorkView）。 */
export function Layout({ workId, onBack }: LayoutProps) {
  const server = useServer();
  const liveAgents = useComposerAgentOptions();
  const [detail, setDetail] = useState<AgentWorkDetailView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeSendRef = useRef<SendHandle | null>(null);
  const [sideTab, setSideTab] = useState<SideTab | null>("results");
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const detailRef = useRef<AgentWorkDetailView | null>(null);
  const persistTimerRef = useRef<number | null>(null);
  const loadGenerationRef = useRef(0);
  const applyRef = useRef<(next: AgentWorkDetailView, options?: { hydrate?: boolean }) => void>(
    () => undefined,
  );

  const splitRef = useRef<HTMLDivElement>(null);
  const [chatWidth, setChatWidth] = useState(DEFAULT_CHAT_WIDTH);
  const [resizing, setResizing] = useState(false);
  const sideOpen = sideTab != null;

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
    (next: AgentWorkDetailView, options?: { hydrate?: boolean }) => {
      detailRef.current = next;
      setDetail(next);
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

  useEffect(() => {
    if (!server.ready) return;

    const generation = ++loadGenerationRef.current;
    let cancelled = false;
    mountCountByWork.set(workId, (mountCountByWork.get(workId) ?? 0) + 1);
    setLoading(true);
    setError(null);
    setDetail(null);
    detailRef.current = null;
    setSideTab("results");
    setSelectedStepId(null);

    void loadAgentWorkDetail(workId)
      .then(async (result) => {
        if (cancelled || generation !== loadGenerationRef.current) return;
        applyRef.current(result.detail, { hydrate: true });
        if (!result.pendingSend) return;

        clearWorkDraft(workId);
        let handle = autoSendByWork.get(workId);
        if (!handle) {
          handle = send(result.detail, result.pendingSend, (next) => {
            if (generation !== loadGenerationRef.current) return;
            applyRef.current(next);
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
  }, [workId, server.ready]);

  const handleSideTabChange = useCallback((tab: SideTab) => {
    setSideTab((current) => (current === tab ? null : tab));
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

  const handleSend = useCallback(
    async (payload: ComposerSubmitPayload) => {
      const current = detailRef.current;
      if (!current || activeSendRef.current) return;
      setError(null);
      setSelectedStepId(null);
      const merged: ComposerSubmitPayload = {
        ...payload,
        agent_id: current.composer_agent_id ?? payload.agent_id,
        model_id: current.composer_model_id ?? payload.model_id,
      };
      const handle = send(current, merged, applyDetailUpdate);
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
      setSelectedStepId(null);

      const payload: ComposerSubmitPayload = {
        message: content,
        agent_id: truncated.composer_agent_id ?? "",
        model_id: truncated.composer_model_id,
        attachments: [],
      };
      const handle = send(truncated, payload, applyDetailUpdate);
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

  const clampWidth = useCallback((width: number) => {
    const splitWidth = splitRef.current?.clientWidth ?? window.innerWidth;
    const max = Math.min(MAX_CHAT_WIDTH, splitWidth - 8 - 320);
    return Math.max(MIN_CHAT_WIDTH, Math.min(width, max));
  }, []);

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = chatWidth;
      setResizing(true);
      const onMove = (moveEvent: globalThis.PointerEvent) => {
        setChatWidth(clampWidth(startWidth + (moveEvent.clientX - startX)));
      };
      const onUp = () => {
        setResizing(false);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [chatWidth, clampWidth],
  );

  if (loading && !detail) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <Card className="w-full max-w-sm">
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
            <CardTitle className="text-sm font-medium">加载工作区…</CardTitle>
            <CardDescription>正在同步 Agent 任务</CardDescription>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <Card className="w-full max-w-sm border-dashed">
          <CardContent className="py-10 text-center">
            <CardTitle className="text-sm font-medium text-foreground">
              {error ? "加载失败" : "未找到该 AI 工作"}
            </CardTitle>
            <CardDescription className="mt-2">{error ?? "请返回重试或选择其他任务"}</CardDescription>
          </CardContent>
        </Card>
      </div>
    );
  }

  const composerAgents =
    detail.composer_agents.length > 0 ? detail.composer_agents : liveAgents;
  const sidePanel =
    sideTab === "results" ? (
      <Products products={detail.products} />
    ) : (
      <Settings
        agents={composerAgents}
        agentId={detail.composer_agent_id ?? null}
        modelId={detail.composer_model_id ?? null}
        disabled={!detail.can_send}
        onChange={handleSettingsChange}
      />
    );

  return (
    <>
    <div
      ref={splitRef}
      className={cn(
        "flex h-full min-h-0 min-w-0 overflow-hidden bg-[color-mix(in_srgb,var(--bg-panel)_72%,transparent)]",
        resizing && "cursor-col-resize select-none",
      )}
    >
      <aside className="flex h-full w-14 shrink-0 flex-col items-center gap-1 border-r border-border/70 bg-card py-3">
        <Button variant="ghost" size="icon-sm" onClick={onBack} aria-label="返回首页">
          <ArrowLeft className="size-4" />
        </Button>
        <div className="mt-3 flex flex-col items-center gap-1">
          <RailTab
            label="结果"
            active={sideTab === "results"}
            onClick={() => handleSideTabChange("results")}
            icon={<Package className="size-4" />}
          />
          <RailTab
            label="设置"
            active={sideTab === "settings"}
            onClick={() => handleSideTabChange("settings")}
            icon={<Settings2 className="size-4" />}
          />
        </div>
      </aside>

      <div
        className={cn(
          "flex min-h-0 min-w-0 flex-col overflow-hidden bg-card",
          sideOpen ? "shrink-0 border-r border-border/70" : "flex-1",
        )}
        style={sideOpen ? { width: chatWidth } : undefined}
      >
        <ChatPane
          detail={detail}
          busy={!detail.can_send}
          error={error}
          selectedStepId={selectedStepId}
          onSend={(payload) => void handleSend(payload)}
          onCancel={handleCancel}
          onSelectStep={(step: AgentWorkStepView) => setSelectedStepId(step.id)}
          onResubmitUser={(messageId, content) => void handleResubmitUser(messageId, content)}
        />
      </div>

      {sideOpen ? (
        <>
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="调整聊天面板宽度"
            className={cn(
              "relative z-10 min-h-0 w-2 shrink-0 cursor-col-resize bg-transparent",
              "before:absolute before:inset-y-0 before:left-1/2 before:w-px before:-translate-x-1/2 before:bg-border",
              "hover:before:bg-foreground/25",
            )}
            onPointerDown={handlePointerDown}
          />
          <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
            {sidePanel}
          </div>
        </>
      ) : null}
    </div>
      <ProductPreviewHost />
    </>
  );
}

function RailTab({
  label,
  active,
  onClick,
  icon,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "relative flex w-12 flex-col items-center gap-0.5 rounded-md px-1 py-2 text-[10px] transition-colors",
        active
          ? "bg-secondary text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

/** @deprecated 使用 Layout */
export const View = Layout;
export const AiWorkView = Layout;
