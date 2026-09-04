import type { AgentBrowserFrameView, AgentBrowserLiveView } from "@/contracts/ai-work";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BrowserFrameViewer } from "./browser-frame-viewer";
import { BrowserHistoryStrip, type BrowserSelection } from "./browser-history-strip";
import { WorkStatusBadge } from "./work-status-badge";

interface AgentBrowserPanelProps {
  live: AgentBrowserLiveView;
  history: AgentBrowserFrameView[];
  selection: BrowserSelection;
  onSelect: (selection: BrowserSelection) => void;
  /** 嵌入工作区 Tab 时隐藏外层标题。 */
  embedded?: boolean;
}

export function AgentBrowserPanel({
  live,
  history,
  selection,
  onSelect,
  embedded = false,
}: AgentBrowserPanelProps) {
  const selectedFrame =
    selection.kind === "history"
      ? history.find((frame) => frame.id === selection.frameId) ?? null
      : null;

  const viewer = selectedFrame ? (
    <BrowserFrameViewer target={{ mode: "history", frame: selectedFrame }} fill={embedded} />
  ) : (
    <BrowserFrameViewer target={{ mode: "live", live }} fill={embedded} />
  );

  const progressHint =
    selection.kind === "live" && live.progress_hint
      ? live.progress_hint
      : selectedFrame?.label
        ? selectedFrame.label
        : null;

  if (embedded) {
    return (
      <div className="flex h-full min-h-0 flex-col overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden p-4 pb-2">
          <div className="min-h-0 flex-1 overflow-hidden">{viewer}</div>
          {progressHint ? (
            <p className="shrink-0 truncate text-xs text-muted-foreground">{progressHint}</p>
          ) : null}
        </div>

        <BrowserHistoryStrip
          history={history}
          live={live}
          selection={selectedFrame ? selection : { kind: "live" }}
          onSelect={onSelect}
          collapsible
          defaultOpen={false}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">Agent 浏览</h2>
          <p className="text-xs text-muted-foreground">分步回看已访问页面，当前页实时同步</p>
        </div>
        <WorkStatusBadge label={live.status.label} badgeClass={live.status.badge_class} />
      </header>

      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-3 p-4">
          {viewer}
          <BrowserHistoryStrip
            history={history}
            live={live}
            selection={selectedFrame ? selection : { kind: "live" }}
            onSelect={onSelect}
          />
          {progressHint ? <p className="text-xs text-muted-foreground">{progressHint}</p> : null}
        </div>
      </ScrollArea>
    </div>
  );
}
