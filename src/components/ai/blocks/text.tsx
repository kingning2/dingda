/**
 * 正文块：直接展示，不折叠；流式用 CharReveal。
 */

import { MarkdownRenderer } from "../markdown";
import { useRevealText } from "../useRevealText";

export interface TextBlockProps {
  text: string;
  streaming: boolean;
}

export function TextBlock({ text, streaming }: TextBlockProps) {
  const display = useRevealText(text, streaming);
  if (!text.trim() && !streaming) return null;

  return (
    <div className="grid max-w-none grid-cols-[1rem_minmax(0,1fr)] gap-2 text-[14px] leading-relaxed text-foreground">
      <span className="pt-px text-muted-foreground/70">•</span>
      <div className="min-w-0">
        {display.trim() ? <MarkdownRenderer content={display} /> : null}
      </div>
    </div>
  );
}
