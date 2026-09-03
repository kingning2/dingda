import { useCallback, useEffect, useRef, useState } from "react";
import { isTauri } from "@tauri-apps/api/core";
import type { ComposerSubmitPayload } from "@/contracts/composer";
import type { AgentWorkDetailView, AgentWorkStepView } from "@/contracts/ai-work";
import { AiWorkSplit } from "./ai-work-split";
import { AgentChatPanel } from "./agent-chat-panel";
import { AgentWorkspacePanel, type WorkspaceTab } from "./agent-workspace-panel";
import type { BrowserSelection } from "./browser-history-strip";
import { sendAgentWorkViaCli } from "./agent-cli-send";
import { mockAgentWorkSend, mockFetchAgentWorkDetail } from "./mock-api";
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

export function AiWorkView({ workId, onBack }: AiWorkViewProps) {
  const [detail, setDetail] = useState<AgentWorkDetailView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("process");
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [browserSelection, setBrowserSelection] = useState<BrowserSelection>({ kind: "live" });
  const pendingDetailRef = useRef<AgentWorkDetailView | null>(null);
  const detailFrameRef = useRef<number | null>(null);
  const hasDetailRef = useRef(false);

  const applyDetailUpdate = useCallback((next: AgentWorkDetailView) => {
    pendingDetailRef.current = next;

    const commit = () => {
      const pending = pendingDetailRef.current;
      if (!pending) return;
      pendingDetailRef.current = null;
      setDetail(pending);
      setLoading(false);
      hasDetailRef.current = true;
      if (pending.recommendations.items.length > 0 && pending.can_send) {
        setWorkspaceTab("results");
      }
    };

    // 首次加载同步提交，避免 loading 已结束但 detail 仍为 null
    if (!hasDetailRef.current) {
      commit();
      return;
    }

    if (detailFrameRef.current !== null) return;

    detailFrameRef.current = requestAnimationFrame(() => {
      detailFrameRef.current = null;
      commit();
    });
  }, []);

  useEffect(() => {
    return () => {
      if (detailFrameRef.current !== null) {
        cancelAnimationFrame(detailFrameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    hasDetailRef.current = false;
    pendingDetailRef.current = null;
    setLoading(true);
    setError(null);
    setDetail(null);
    setWorkspaceTab("process");
    setSelectedStepId(null);
    setBrowserSelection({ kind: "live" });

    void mockFetchAgentWorkDetail(
      workId,
      (progress) => {
        if (!cancelled) applyDetailUpdate(progress);
      },
      { autoSend: !isTauri() },
    )
      .then(async (result) => {
        if (cancelled) return;
        applyDetailUpdate(result.detail);
        if (result.pendingSend && isTauri()) {
          try {
            await sendAgentWorkViaCli(result.detail, result.pendingSend, applyDetailUpdate);
          } catch {
            if (!cancelled) setError("发送失败，请重试");
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("加载 AI 工作详情失败");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (detailFrameRef.current !== null) {
        cancelAnimationFrame(detailFrameRef.current);
        detailFrameRef.current = null;
      }
    };
  }, [workId, applyDetailUpdate]);

  const handleSelectStep = useCallback(
    (step: AgentWorkStepView) => {
      if (!detail) return;
      setSelectedStepId(step.id);
      setBrowserSelection(browserSelectionForStep(detail, step));
      setWorkspaceTab("process");
    },
    [detail],
  );

  const handleSend = useCallback(
    async (payload: ComposerSubmitPayload) => {
      if (!detail) return;
      setError(null);
      setSelectedStepId(null);
      setWorkspaceTab("process");
      setBrowserSelection({ kind: "live" });
      try {
        if (isTauri()) {
          await sendAgentWorkViaCli(detail, payload, applyDetailUpdate);
        } else {
          const result = await mockAgentWorkSend(
            {
              work_id: detail.work_id,
              message: payload.message,
              agent_id: payload.agent_id,
              model_id: payload.model_id,
              attachments: payload.attachments,
            },
            applyDetailUpdate,
          );
          applyDetailUpdate(result);
        }
      } catch {
        setError("发送失败，请重试");
      }
    },
    [detail, applyDetailUpdate],
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

  return (
    <AiWorkSplit
      chat={
        <AgentChatPanel
          detail={detail}
          busy={!detail.can_send}
          selectedStepId={selectedStepId}
          onBack={onBack}
          onSend={(payload) => void handleSend(payload)}
          onSelectStep={handleSelectStep}
        />
      }
      workspace={
        <AgentWorkspacePanel
          live={detail.browser_live}
          history={detail.browser_history}
          recommendations={detail.recommendations}
          tab={workspaceTab}
          onTabChange={setWorkspaceTab}
          selection={browserSelection}
          onSelect={setBrowserSelection}
        />
      }
    />
  );
}
