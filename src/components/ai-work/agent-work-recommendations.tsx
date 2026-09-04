import type { AgentWorkRecommendationsView } from "@/contracts/ai-work";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { WorkStatusBadge } from "./work-status-badge";
import { cn } from "@/lib/utils";

interface AgentWorkRecommendationsPanelProps {
  recommendations: AgentWorkRecommendationsView;
  className?: string;
}

function RecommendationCard({ item }: { item: AgentWorkRecommendationsView["items"][number] }) {
  return (
    <Card size="sm" className="ring-border/70">
      <CardContent className="space-y-3">
        <div className="flex gap-3">
          <Card className="size-16 shrink-0 items-center justify-center ring-0" size="sm">
            <CardContent className="flex size-full items-center justify-center p-0 text-[10px] text-muted-foreground">
              图
            </CardContent>
          </Card>
          <div className="min-w-0 flex-1">
            <CardTitle className="line-clamp-2 text-sm leading-snug">{item.title}</CardTitle>
            <p className="mt-1 text-lg font-semibold text-foreground">{item.price}</p>
            <CardDescription className="truncate text-xs">
              {[item.seller, item.location].filter(Boolean).join(" · ")}
            </CardDescription>
          </div>
        </div>

        <Separator />

        <div className="space-y-2">
          <div>
            <p className="text-[11px] font-medium text-muted-foreground">推荐理由</p>
            <p className="mt-0.5 text-sm leading-relaxed text-foreground">{item.recommendation_reason}</p>
          </div>
          <div>
            <p className="text-[11px] font-medium text-muted-foreground">推荐依据</p>
            <p className="mt-0.5 text-sm leading-relaxed text-foreground">{item.recommendation_basis}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function AgentWorkRecommendationsPanel({
  recommendations,
  className,
}: AgentWorkRecommendationsPanelProps) {
  const { items, total, status, summary } = recommendations;

  return (
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-border/70 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">推荐结果</h2>
          <p className="truncate text-xs text-muted-foreground">
            {summary ?? status.hint ?? "综合抓取数据后的最终推荐"}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-0.5">
          <WorkStatusBadge label={status.label} badgeClass={status.badge_class} />
          {total > 0 ? <span className="text-xs text-muted-foreground">共推荐 {total} 款</span> : null}
        </div>
      </header>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-4">
          {items.length === 0 ? (
            <Card className="border-dashed ring-0">
              <CardContent className="py-16 text-center text-sm text-muted-foreground">
                {status.hint ?? "任务完成后，这里会展示推荐商品及依据"}
              </CardContent>
            </Card>
          ) : (
            <ul className="space-y-3">
              {items.map((item) => (
                <li key={item.id}>
                  <RecommendationCard item={item} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
