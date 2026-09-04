import type { AgentBrowserFrameView, AgentBrowserLiveView, AgentWorkRecommendationsView } from "@/contracts/ai-work";
import { AgentBrowserPanel } from "./agent-browser-panel";
import { AgentWorkRecommendationsPanel } from "./agent-work-recommendations";
import type { BrowserSelection } from "./browser-history-strip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type WorkspaceTab = "process" | "results";

interface AgentWorkspacePanelProps {
  live: AgentBrowserLiveView;
  history: AgentBrowserFrameView[];
  recommendations: AgentWorkRecommendationsView;
  tab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
  selection: BrowserSelection;
  onSelect: (selection: BrowserSelection) => void;
}

export function AgentWorkspacePanel({
  live,
  history,
  recommendations,
  tab,
  onTabChange,
  selection,
  onSelect,
}: AgentWorkspacePanelProps) {
  return (
    <Tabs
      value={tab}
      onValueChange={(value) => onTabChange(value as WorkspaceTab)}
      className="flex h-full min-h-0 flex-col gap-0"
    >
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
        <TabsList aria-label="工作区视图">
          <TabsTrigger value="process">过程</TabsTrigger>
          <TabsTrigger value="results">结果</TabsTrigger>
        </TabsList>
        <span className="text-xs text-muted-foreground">
          {tab === "process" ? "浏览 Agent 访问过的页面" : `推荐 ${recommendations.total} 款`}
        </span>
      </header>

      <TabsContent value="process" className="mt-0 flex min-h-0 flex-1 flex-col overflow-hidden">
        <AgentBrowserPanel
          live={live}
          history={history}
          selection={selection}
          onSelect={onSelect}
          embedded
        />
      </TabsContent>

      <TabsContent value="results" className="mt-0 min-h-0 flex-1 overflow-hidden">
        <AgentWorkRecommendationsPanel recommendations={recommendations} />
      </TabsContent>
    </Tabs>
  );
}
