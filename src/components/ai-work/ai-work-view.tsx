import { useCallback, useEffect, useRef, useState } from "react";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import type { AgentWorkDetailView, AgentWorkStepView } from "@/contracts/ai-work";
import { supportsExternalAgents } from "@/lib/capabilities";
import { putAgentWorkDetail } from "@/lib/agent-api";
import { useServer } from "@/providers/server-provider";
import { loadAgentWorkDetail } from "./agent-work-loader";
import { clearWorkDraft, stashWorkSnapshot } from "./work-draft";
import { AiWorkSplit } from "./ai-work-split";
import { AgentChatPanel } from "./agent-chat-panel";
import { AgentWorkspacePanel, type WorkspaceTab } from "./agent-workspace-panel";
import type { BrowserSelection } from "./browser-history-strip";
import { sendAgentWorkViaCli } from "./agent-cli-send";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

interface AiWorkViewProps {
  workId: string;
  onBack?: () => void;
}

function browserSelectionForStep(detail: AgentWorkDetailView, step: AgentWorkStepView): BrowserSelection {
  if (!step.browser_frame_id) return { kind: "live" };
  if (step.browser_frame_id === detail.browser_live.frame_id) return { kind: "live" };
  return { kind: "history", frameId: step.browser_frame_id };
}

function isBlankBrowserUrl(url: string | null | undefined): boolean {
  const trimmed = (url ?? "").trim();
  return trimmed.length === 0 || trimmed === "about:blank";
}

/** 有真实浏览页或推荐结果时才显示右侧工作区（空 about:blank / 待命占位不算）。 */
function hasWorkspaceContent(detail: AgentWorkDetailView): boolean {
  const hasProcess =
    !isBlankBrowserUrl(detail.browser_live.url) ||
    detail.browser_history.some(
      (frame) => !isBlankBrowserUrl(frame.url) || Boolean(frame.screenshot_url),
    );
  const hasResults = detail.recommendations.items.length > 0;
  return hasProcess || hasResults;
}

const PERSIST_DEBOUNCE_MS = 400;

export function AiWorkView({ workId, onBack }: AiWorkViewProps) {
  const server = useServer();
  const [detail, setDetail] = useState<AgentWorkDetailView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("process");
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [browserSelection, setBrowserSelection] = useState<BrowserSelection>({ kind: "live" });
  const detailRef = useRef<AgentWorkDetailView | null>(null);
  const persistTimerRef = useRef<number | null>(null);
  const loadGenerationRef = useRef(0);

  const schedulePersist = useCallback((next: AgentWorkDetailView) => {
    if (persistTimerRef.current !== null) {
      window.clearTimeout(persistTimerRef.current);
    }
    persistTimerRef.current = window.setTimeout(() => {
      persistTimerRef.current = null;
      const snapshot = detailRef.current;
      if (!snapshot) return;
      stashWorkSnapshot(snapshot);
      void putAgentWorkDetail(snapshot).catch(() => {
        // 落库失败不打断对话
      });
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
    void putAgentWorkDetail(snapshot, {
      keepalive,
      // keepalive 场景下页面可能马上卸掉，不要弹窗
    }).catch(() => {
      // 落库失败不打断对话；本地 snapshot 已写入
    });
  }, []);

  const applyDetailUpdate = useCallback(
    (next: AgentWorkDetailView, options?: { hydrate?: boolean }) => {
      detailRef.current = next;
      setDetail(next);
      setLoading(false);
      // 每次变更同步写本地快照，保证 Ctrl+R 能立刻读回
      stashWorkSnapshot(next);
      if (options?.hydrate) {
        // 刚从库/快照加载，不必立刻再 PUT（避免空壳覆盖）
      } else if (next.can_send || next.messages.length > 0) {
        flushPersist(next, false);
      } else {
        schedulePersist(next);
      }
      if (next.recommendations.items.length > 0 && next.can_send) {
        setWorkspaceTab("results");
      }
    },
    [schedulePersist, flushPersist],
  );

  useEffect(() => {
    const onPageHide = () => {
      flushPersist(undefined, true);
    };
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("beforeunload", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("beforeunload", onPageHide);
      flushPersist(undefined, true);
    };
  }, [flushPersist]);

  useEffect(() => {
    if (!server.ready) return;

    const generation = ++loadGenerationRef.current;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetail(null);
    detailRef.current = null;
    setWorkspaceTab("process");
    setSelectedStepId(null);
    setBrowserSelection({ kind: "live" });

    void loadAgentWorkDetail(workId)
      .then(async (result) => {
        if (cancelled || generation !== loadGenerationRef.current) return;
        applyDetailUpdate(result.detail, { hydrate: true });
        if (result.pendingSend && supportsExternalAgents()) {
          clearWorkDraft(workId);
          try {
            await sendAgentWorkViaCli(result.detail, result.pendingSend, (next) => {
              if (cancelled || generation !== loadGenerationRef.current) return;
              applyDetailUpdate(next);
            });
          } catch (err) {
            if (!cancelled && generation === loadGenerationRef.current) {
              setError(err instanceof Error ? err.message : "发送失败，请重试");
            }
          }
        } else if (result.pendingSend && !supportsExternalAgents()) {
          clearWorkDraft(workId);
          if (!cancelled && generation === loadGenerationRef.current) {
            setError("外部 Agent 仅桌面端可用");
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
    };
  }, [workId, applyDetailUpdate, server.ready]);

  const handleSelectStep = useCallback(
    (step: AgentWorkStepView) => {
      const current = detailRef.current;
      if (!current) return;
      setSelectedStepId(step.id);
      setBrowserSelection(browserSelectionForStep(current, step));
      setWorkspaceTab("process");
    },
    [],
  );

  const handleSend = useCallback(
    async (payload: ComposerSubmitPayload) => {
      const current = detailRef.current;
      if (!current) return;
      setError(null);
      setSelectedStepId(null);
      setWorkspaceTab("process");
      setBrowserSelection({ kind: "live" });
      if (!supportsExternalAgents()) {
        setError("外部 Agent 仅桌面端可用");
        return;
      }
      try {
        await sendAgentWorkViaCli(current, payload, applyDetailUpdate);
      } catch (err) {
        setError(err instanceof Error ? err.message : "发送失败，请重试");
      }
    },
    [applyDetailUpdate],
  );

  if (loading && !detail) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <Card className="w-full max-w-sm">
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
            <CardTitle className="text-sm font-medium">加载工作区…</CardTitle>
            <CardDescription>正在同步 Agent 任务与浏览记录</CardDescription>
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

  const showWorkspace = hasWorkspaceContent(detail);

  return (
    <AiWorkSplit
      showWorkspace={showWorkspace}
      chat={
        <AgentChatPanel
          detail={detail}
          busy={!detail.can_send}
          error={error}
          selectedStepId={selectedStepId}
          onBack={onBack}
          onSend={(payload) => void handleSend(payload)}
          onSelectStep={handleSelectStep}
        />
      }
      workspace={
        showWorkspace ? (
          <AgentWorkspacePanel
            live={detail.browser_live}
            history={detail.browser_history}
            recommendations={detail.recommendations}
            tab={workspaceTab}
            onTabChange={setWorkspaceTab}
            selection={browserSelection}
            onSelect={setBrowserSelection}
          />
        ) : null
      }
    />
  );
}
