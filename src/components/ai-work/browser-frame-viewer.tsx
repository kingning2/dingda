import { Globe, Loader2, Lock, RefreshCw } from "lucide-react";
import type { AgentBrowserFrameView, AgentBrowserLiveView } from "@/contracts/ai-work";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { MockPagePreview } from "./mock-page-preview";

type ViewerTarget =
  | { mode: "live"; live: AgentBrowserLiveView }
  | { mode: "history"; frame: AgentBrowserFrameView };

interface BrowserFrameViewerProps {
  target: ViewerTarget;
  /** 嵌入过程 Tab 时铺满剩余高度，避免整页滚动。 */
  fill?: boolean;
}

export function BrowserFrameViewer({ target, fill = false }: BrowserFrameViewerProps) {
  const url = target.mode === "live" ? target.live.url : target.frame.url;
  const title = target.mode === "live" ? target.live.title : target.frame.title;
  const focusLabel = target.mode === "live" ? target.live.focus_label : target.frame.focus_label;
  const screenshotUrl =
    target.mode === "live" ? target.live.screenshot_url : target.frame.screenshot_url;
  const isBlank = url === "about:blank";
  const isLive = target.mode === "live";
  const liveHint = isLive ? target.live.status.hint : null;
  const progressHint = isLive ? target.live.progress_hint : target.frame.label;
  const canOpenUrl = !isBlank;

  return (
    <Card className={cn("gap-0 overflow-hidden py-0 shadow-sm", fill && "flex h-full min-h-0 flex-col")}>
      <CardContent className="flex items-center gap-2 border-b border-border/70 bg-muted/30 px-3 py-2">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <span className="size-2.5 rounded-full bg-red-400/90" />
          <span className="size-2.5 rounded-full bg-amber-400/90" />
          <span className="size-2.5 rounded-full bg-emerald-400/90" />
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border/80 bg-background px-2.5 py-1.5 text-xs text-muted-foreground">
          <Lock className="size-3.5 shrink-0" />
          {canOpenUrl ? (
            <Badge
              variant="link"
              className="h-auto min-w-0 flex-1 justify-start truncate px-0 font-mono text-[11px] font-normal text-foreground/80"
              render={<a href={url} target="_blank" rel="noopener noreferrer" />}
            >
              {url}
            </Badge>
          ) : (
            <span className="truncate font-mono text-[11px] text-foreground/80">{url}</span>
          )}
        </div>
        <Button variant="ghost" size="icon-xs" aria-label="刷新" disabled>
          <RefreshCw className="size-3.5" />
        </Button>
      </CardContent>

      <CardContent className="flex items-center justify-between gap-3 border-b border-border/60 py-2 text-xs text-muted-foreground">
        <div className="flex min-w-0 items-center gap-2">
          <Globe className="size-3.5 shrink-0" />
          <span className="truncate font-medium text-foreground">{title}</span>
        </div>
        {focusLabel ? <Badge variant="secondary">{focusLabel}</Badge> : null}
      </CardContent>

      <CardContent
        className={cn(
          "relative bg-[linear-gradient(180deg,color-mix(in_srgb,var(--muted)_55%,white),white)] p-0",
          fill ? "min-h-0 flex-1" : "min-h-[300px]",
        )}
      >
        {isBlank ? (
          <Card
            className={cn(
              "rounded-none border-0 bg-transparent shadow-none ring-0",
              fill ? "flex h-full min-h-0" : "min-h-[300px]",
            )}
          >
            <CardContent className="flex h-full min-h-0 flex-col items-center justify-center gap-2 px-6 py-8 text-center">
              <Globe className="size-8 text-muted-foreground/40" />
              <CardDescription>{progressHint ?? "等待 Agent 打开网页"}</CardDescription>
            </CardContent>
          </Card>
        ) : screenshotUrl ? (
          <img
            src={screenshotUrl}
            alt={title}
            className={cn(
              "w-full",
              fill ? "h-full object-contain object-top" : "object-cover object-top",
            )}
            decoding="async"
          />
        ) : (
          <div className={cn(fill && "h-full overflow-hidden")}>
            <MockPagePreview title={title} focusLabel={focusLabel} />
          </div>
        )}

        {isLive && liveHint ? (
          <Badge
            variant="outline"
            className="absolute right-3 bottom-3 gap-1.5 bg-background/95 py-1.5 pr-3 pl-2.5 shadow-sm"
          >
            <Loader2 className="size-3.5 animate-spin text-sky-600" />
            {liveHint}
          </Badge>
        ) : null}

        {!isLive ? (
          <Badge variant="outline" className="absolute top-3 left-3 bg-background/95 text-[11px] shadow-sm">
            历史截图
          </Badge>
        ) : null}
      </CardContent>
    </Card>
  );
}
