/**
 * 正文块：直接展示，不折叠；流式用 CharReveal。
 *
 * 职责：
 *   渲染助手正文（text 块），流式期间逐字揭示，结束后一次性展示。
 *
 * 设计说明：
 *   - 空正文且非流式时返回 null：后端可能给只有空白的 content，
 *     渲染空块会在时间线上留出空白间隙。
 *   - 文件末尾自注册，Chat 通过注册表取用，不认识本组件。
 */

import { MarkdownRenderer } from "../markdown";
import { useRevealText } from "./use-reveal-text";
import { registerBlock } from "../chat/registry";
import type { ChatBlockProps } from "../chat/types";

/** 纯文本块：助手正文的逐字渲染容器。 */
export function TextBlock({ block }: ChatBlockProps<"text">) {
  const display = useRevealText(block.text, block.streaming);
  if (!block.text.trim() && !block.streaming) return null;

  return (
    <div className="grid max-w-none grid-cols-[1rem_minmax(0,1fr)] gap-2 text-[14px] leading-relaxed text-foreground">
      <span className="pt-px text-muted-foreground/70">•</span>
      <div className="min-w-0">
        {display.trim() ? <MarkdownRenderer content={display} /> : null}
      </div>
    </div>
  );
}

registerBlock("text", TextBlock);
