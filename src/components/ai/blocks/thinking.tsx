/**
 * 思考块：Foldable + 100ms 合并 + ~2s CharReveal；历史挂载不重播。
 */

import { useEffect, useRef, useState } from "react";
import { Collapse } from "../Collapse";
import { MarkdownRenderer } from "../markdown";
import { useRevealText } from "../useRevealText";
import { useThinkingFollow } from "../useThinkingFollow";

export interface ThinkingBlockProps {
  text: string;
  streaming: boolean;
  startedAt?: string | null;
  durationSec?: number | null;
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
  text,
  streaming,
  startedAt = null,
  durationSec = null,
}: ThinkingBlockProps) {
  const [liveSec, setLiveSec] = useState(() => elapsedSeconds(startedAt));
  const bodyRef = useRef<HTMLDivElement>(null);
  const display = useRevealText(text, streaming);
  useThinkingFollow(bodyRef, streaming);

  useEffect(() => {
    if (!streaming || !startedAt) {
      setLiveSec(elapsedSeconds(startedAt));
      return;
    }
    setLiveSec(elapsedSeconds(startedAt));
    const timer = window.setInterval(() => setLiveSec(elapsedSeconds(startedAt)), 1000);
    return () => window.clearInterval(timer);
  }, [streaming, startedAt]);

  if (!text.trim() && !streaming && durationSec == null) return null;
  // 尚无思考正文时不占位；外层「工作中…」负责等待态
  if (!text.trim() && streaming) return null;

  const displaySec = streaming ? liveSec : (durationSec ?? liveSec);
  const title = streaming
    ? `思考中${displaySec > 0 ? ` · ${formatDuration(displaySec)}` : "…"}`
    : displaySec > 0
      ? `思考了 ${formatDuration(displaySec)}`
      : "思考";

  const body = display.trim() ? (
    <div className="border-l border-border/70 pl-3 text-muted-foreground">
      <MarkdownRenderer content={display} className="text-[12px]" />
    </div>
  ) : null;

  return (
    <Collapse
      title={title}
      lifecycleOpen={streaming}
      bodyRef={bodyRef}
      bodyClassName="max-h-56 overflow-y-auto"
    >
      {body}
    </Collapse>
  );
}
