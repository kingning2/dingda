import { useEffect, useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { MarkdownRenderer } from "../markdown";
import { TypewriterCursor } from "../message/typewriter";

interface ThinkingBlockProps {
  content: string;
  title?: string;
  defaultOpen?: boolean;
  busy?: boolean;
  /** 开始时刻（ISO 或可被 Date 解析）。busy 时用于实时秒数。 */
  startedAt?: string | null;
  /** 已结束时的总秒数（落库回放）。 */
  durationSec?: number | null;
  className?: string;
}

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}分${s}s`;
}

function elapsedSeconds(startedAt: string | null | undefined): number {
  if (!startedAt) return 0;
  const start = Date.parse(startedAt);
  if (Number.isNaN(start)) return 0;
  return Math.max(0, Math.floor((Date.now() - start) / 1000));
}

export function ThinkingBlock({
  content,
  title = "思考过程",
  defaultOpen = false,
  busy = false,
  startedAt = null,
  durationSec = null,
  className,
}: ThinkingBlockProps) {
  const [open, setOpen] = useState(defaultOpen || busy);
  const [liveSec, setLiveSec] = useState(() => elapsedSeconds(startedAt));

  useEffect(() => {
    if (!busy || !startedAt) {
      setLiveSec(elapsedSeconds(startedAt));
      return;
    }
    setLiveSec(elapsedSeconds(startedAt));
    const timer = window.setInterval(() => {
      setLiveSec(elapsedSeconds(startedAt));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [busy, startedAt]);

  if (!content.trim() && !busy && durationSec == null) return null;

  const displaySec = busy ? liveSec : (durationSec ?? liveSec);
  const timeLabel =
    displaySec > 0 || busy
      ? busy
        ? `已思考 ${formatDuration(displaySec)}`
        : `思考了 ${formatDuration(displaySec)}`
      : null;

  return (
    <div className={cn("rounded-lg border border-border/70 bg-muted/30", className)}>
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="flex flex-wrap items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Sparkles className="size-3.5 text-violet-500" />
          {title}
          {busy ? <span className="text-[11px] font-normal text-sky-600">进行中</span> : null}
          {timeLabel ? (
            <span className="text-[11px] font-normal text-muted-foreground/90">{timeLabel}</span>
          ) : null}
        </span>
        <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className="border-t border-border/60 px-3 py-2 text-muted-foreground">
          {content.trim() ? (
            <>
              <MarkdownRenderer content={content} className="text-xs" />
              {busy ? <TypewriterCursor /> : null}
            </>
          ) : busy ? (
            <p className="text-xs">思考中…</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
