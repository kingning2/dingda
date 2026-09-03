import { useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { MarkdownRenderer } from "../markdown";
import { TypewriterCursor } from "../message/typewriter";

interface ThinkingBlockProps {
  content: string;
  title?: string;
  defaultOpen?: boolean;
  busy?: boolean;
  className?: string;
}

export function ThinkingBlock({
  content,
  title = "思考过程",
  defaultOpen = false,
  busy = false,
  className,
}: ThinkingBlockProps) {
  const [open, setOpen] = useState(defaultOpen || busy);

  if (!content.trim() && !busy) return null;

  return (
    <div className={cn("rounded-lg border border-border/70 bg-muted/30", className)}>
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Sparkles className="size-3.5 text-violet-500" />
          {title}
          {busy ? <span className="text-[11px] font-normal text-sky-600">进行中…</span> : null}
        </span>
        <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className="border-t border-border/60 px-3 py-2 text-muted-foreground">
          <MarkdownRenderer content={content} className="text-xs" />
          {busy ? <TypewriterCursor /> : null}
        </div>
      ) : null}
    </div>
  );
}
