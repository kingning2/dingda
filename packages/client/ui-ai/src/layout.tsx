/**
 * AI 工作页：唯一 Layout — 左聊天（调度器）/ 右结果|设置。
 *
 * 职责：页面装配。所有业务逻辑已抽到 `useWorkDetail`（加载/发送/持久化）与
 * `useSidePanel`（侧边栏/分栏），本组件只剩 JSX 组合。
 */

import { useCallback, type ReactNode } from "react";
import { ArrowLeft, Loader2, Package, Settings2 } from "lucide-react";
import type { AgentWorkStepView } from "@v2/contracts/ai-work";
import { useServer } from "@v2/runtime/server-provider";
import { useComposerAgentOptions } from "@v2/ui-composer/composer-agents";
import { Button } from "@v2/ui-primitives/button";
import { Card, CardContent, CardDescription, CardTitle } from "@v2/ui-primitives/card";
import { cn } from "@v2/ui-primitives/utils";
import { Chat } from "./chat/chat";
import { useSidePanel } from "./chat/use-side-panel";
import { useWorkDetail } from "./chat/use-work-detail";
import { ProductPreviewHost } from "./ProductPreviewHost";
import { Products } from "./Products";
import { Settings } from "./Settings";

interface LayoutProps {
  workId: string;
  onBack?: () => void;
}

/** AI 工作页入口（对外 AiWorkView）。 */
export function Layout({ workId, onBack }: LayoutProps) {
  const server = useServer();
  const liveAgents = useComposerAgentOptions();
  const {
    detail,
    loading,
    error,
    runPhase,
    handleSend,
    handleResubmitUser,
    handleCancel,
    handleSettingsChange,
  } = useWorkDetail(workId, server.ready);
  const {
    sideTab,
    selectedStepId,
    setSelectedStepId,
    chatWidth,
    resizing,
    sideOpen,
    handleSideTabChange,
    handlePointerDown,
  } = useSidePanel();

  const handleSelectStep = useCallback(
    (step: AgentWorkStepView) => setSelectedStepId(step.id),
    [setSelectedStepId],
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
            <CardDescription className="mt-2">
              {error ?? "请返回重试或选择其他任务"}
            </CardDescription>
          </CardContent>
        </Card>
      </div>
    );
  }

  const composerAgents =
    detail.composer_agents.length > 0 ? detail.composer_agents : liveAgents;

  const sidePanel =
    sideTab === "results" ? (
      <Products products={detail.products} comparison={detail.comparison ?? null} />
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
          <Chat
            detail={detail}
            agents={composerAgents}
            busy={!detail.can_send}
            runPhase={runPhase}
            error={error}
            selectedStepId={selectedStepId}
            onSend={(payload) => void handleSend(payload)}
            onCancel={handleCancel}
            onSelectStep={handleSelectStep}
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

export const View = Layout;
/** AI 工作页视图别名（供路由装配用）。 */
export const AiWorkView = Layout;
