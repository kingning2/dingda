/**
 * 思考块：Foldable + 100ms 合并 + ~2s CharReveal；历史挂载不重播。
 *
 * 职责：
 *   渲染助手推理过程（thinking 块）：流式期间不显示正文，结束后折叠成一行
 *   「Thought for Ns」摘要，展开才看内容。
 *
 * 设计说明：
 *   - streaming 时返回 null 是有意的：活动阶段由 ChatPane 的 Codex 状态行承担反馈，
 *     推理正文只在结束后保留为可展开摘要，避免同一信息出现两处。
 *   - 文件末尾自注册，Chat 通过注册表取用，不认识本组件。
 */

import { useEffect, useState } from "react";
import { Collapse } from "../Collapse";
import { MarkdownRenderer } from "../markdown";
import { useRevealText } from "../useRevealText";
import { registerBlock } from "../chat/registry";
import type { ChatBlockProps } from "../chat/types";

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

/** 思考块：Codex / Claude 的推理过程，默认折叠。 */
export function ThinkingBlock({ block }: ChatBlockProps<"thinking">) {
  const { text, streaming, startedAt = null, durationSec = null } = block;
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

registerBlock("thinking", ThinkingBlock);
