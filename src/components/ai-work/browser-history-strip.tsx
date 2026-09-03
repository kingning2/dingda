import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import type { AgentBrowserFrameView, AgentBrowserLiveView } from "@/contracts/ai-work";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type BrowserSelection = { kind: "history"; frameId: string } | { kind: "live" };

interface BrowserHistoryStripProps {
  history: AgentBrowserFrameView[];
  live: AgentBrowserLiveView;
  selection: BrowserSelection;
  onSelect: (selection: BrowserSelection) => void;
  /** 过程 Tab 内可折叠，默认收起以留出主预览区。 */
  collapsible?: boolean;
  defaultOpen?: boolean;
  className?: string;
}

export function BrowserHistoryStrip({
  history,
  live,
  selection,
  onSelect,
  collapsible = false,
  defaultOpen = false,
  className,
}: BrowserHistoryStripProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(defaultOpen);
  const liveVisible = live.url !== "about:blank";
  const totalCount = history.length + (liveVisible ? 1 : 0);

  useEffect(() => {
    if (!open) return;
    endRef.current?.scrollIntoView({ behavior: "auto", block: "nearest", inline: "end" });
  }, [history.length, live.frame_id, open]);

  if (totalCount === 0) {
    return null;
  }

  const strip = (
    <div className="flex gap-2 overflow-x-auto pb-0.5 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {history.map((frame, index) => {
        const active = selection.kind === "history" && selection.frameId === frame.id;
        return (
          <Button
            key={frame.id}
            type="button"
            variant="outline"
            className={cn(
              "h-auto w-[132px] shrink-0 flex-col items-stretch gap-0 overflow-hidden p-0",
              active && "border-sky-500 ring-2 ring-sky-500/25",
            )}
            onClick={() => onSelect({ kind: "history", frameId: frame.id })}
          >
            <Card className="w-full gap-0 rounded-none border-0 py-0 shadow-none ring-0">
              <CardContent className="relative aspect-[16/10] bg-muted p-0">
                <img
                  src={frame.screenshot_url}
                  alt={frame.title}
                  className="size-full object-cover object-top"
                />
                <Badge className="absolute top-1.5 left-1.5 bg-background/90 text-[10px] text-muted-foreground">
                  {index + 1}
                </Badge>
              </CardContent>
              <CardContent className="space-y-0.5 px-2 py-1.5 text-left">
                <p className="line-clamp-1 text-[11px] font-medium text-foreground">
                  {frame.label ?? frame.title}
                </p>
                <p className="line-clamp-1 text-[10px] text-muted-foreground">
                  {frame.focus_label ?? frame.url}
                </p>
              </CardContent>
            </Card>
          </Button>
        );
      })}

      {liveVisible ? (
        <Button
          type="button"
          variant="outline"
          className={cn(
            "h-auto w-[132px] shrink-0 flex-col items-stretch gap-0 overflow-hidden p-0",
            selection.kind === "live" && "border-sky-500 ring-2 ring-sky-500/25",
          )}
          onClick={() => onSelect({ kind: "live" })}
        >
          <Card className="w-full gap-0 rounded-none border-0 py-0 shadow-none ring-0">
            <CardContent className="relative aspect-[16/10] bg-muted p-0">
              {live.screenshot_url ? (
                <img
                  src={live.screenshot_url}
                  alt={live.title}
                  className="size-full object-cover object-top"
                />
              ) : (
                <div className="flex size-full items-center justify-center text-[10px] text-muted-foreground">
                  实时
                </div>
              )}
              <Badge className="absolute top-1.5 left-1.5 border-transparent bg-sky-600 text-[10px] text-white">
                当前
              </Badge>
            </CardContent>
            <CardContent className="space-y-0.5 px-2 py-1.5 text-left">
              <p className="line-clamp-1 text-[11px] font-medium text-foreground">{live.title}</p>
              <p className="line-clamp-1 text-[10px] text-muted-foreground">
                {live.focus_label ?? live.progress_hint ?? "进行中"}
              </p>
            </CardContent>
          </Card>
        </Button>
      ) : null}
      <div ref={endRef} className="w-px shrink-0" />
    </div>
  );

  if (!collapsible) {
    return (
      <div className={cn("shrink-0 space-y-2", className)}>
        <div className="flex items-center justify-between gap-2 px-0.5">
          <p className="text-xs font-medium text-foreground">浏览记录</p>
          <p className="text-[11px] text-muted-foreground">每步保留最后一帧截图</p>
        </div>
        {strip}
      </div>
    );
  }

  return (
    <div className={cn("shrink-0 border-t border-border/70 bg-muted/20", className)}>
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-4 py-2.5 text-left"
        onClick={() => setOpen((value) => !value)}
      >
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-xs font-medium text-foreground">浏览记录</span>
          <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
            {totalCount}
          </Badge>
          {!open ? (
            <span className="truncate text-[11px] text-muted-foreground">每步保留最后一帧截图</span>
          ) : null}
        </div>
        <ChevronDown
          className={cn("size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
        />
      </button>
      {open ? <div className="px-4 pb-3">{strip}</div> : null}
    </div>
  );
}
