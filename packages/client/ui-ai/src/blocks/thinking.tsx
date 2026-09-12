/**
 * 思考块：Foldable + 100ms 合并 + ~2s CharReveal；历史挂载不重播。
 */

import { useEffect, useState } from "react";
import { Collapse } from "../Collapse";
import { MarkdownRenderer } from "../markdown";
import { useRevealText } from "../useRevealText";

export interface ThinkingBlockProps {
  text: string;
  streaming: boolean;
  startedAt?: string | null;
  durationSec?: number | null;
}

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) {
    const minutes = Math.floor(sec / 60);
    const seconds = sec % 60;
    return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
  }
  const hours = Math.floor(sec / 3600);
  const minutes = Math.floor((sec % 3600) / 60);
  const seconds = sec % 60;
  return `${hours}h ${String(minutes).padStart(2, "0")}m ${String(seconds).padStart(2, "0")}s`;
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
  const display = useRevealText(text, streaming);

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
  // 活动阶段由 Codex 风格状态行承担，推理正文只在结束后保留为可展开摘要。
  if (streaming) return null;

  const displaySec = streaming ? liveSec : (durationSec ?? liveSec);
  const title = displaySec > 0 ? `Thought for ${formatDuration(displaySec)}` : "Thought";

  const body = display.trim() ? (
    <div className="border-l border-border/70 pl-3 text-muted-foreground/80">
      <MarkdownRenderer content={display} className="text-[12px]" />
    </div>
  ) : null;

  return (
    <Collapse
      title={<span className="italic">• {title}</span>}
      lifecycleOpen={false}
      bodyClassName="max-h-56 overflow-y-auto"
    >
      {body}
    </Collapse>
  );
}
