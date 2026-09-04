import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

type MarkdownCodeProps = ComponentProps<"code"> & {
  inline?: boolean;
};

export function MarkdownCode({ className, children, inline, ...props }: MarkdownCodeProps) {
  const match = /language-(\w+)/.exec(className ?? "");
  const isBlock = Boolean(match) || inline === false;

  if (!isBlock) {
    return (
      <code
        className={cn(
          "break-all rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.9em] text-foreground",
          className,
        )}
        {...props}
      >
        {children}
      </code>
    );
  }

  return (
    <div className="my-2 overflow-hidden rounded-lg border border-border/80 bg-muted/40">
      {match?.[1] ? (
        <div className="border-b border-border/60 px-3 py-1.5 text-[11px] text-muted-foreground">
          {match[1]}
        </div>
      ) : null}
      <pre className="overflow-x-auto p-3 text-xs leading-relaxed">
        <code className={cn("font-mono text-foreground", className)} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
}
