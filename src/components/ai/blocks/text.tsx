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
    <div className="max-w-none text-[14px] leading-relaxed text-foreground">
      {display.trim() ? <MarkdownRenderer content={display} /> : null}
    </div>
  );
}
