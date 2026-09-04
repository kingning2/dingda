import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function MarkdownTable({ className, ...props }: ComponentProps<"table">) {
  return (
    <div className="my-3 w-full overflow-x-auto rounded-lg border border-border/80">
      <table className={cn("w-full min-w-[480px] border-collapse text-sm", className)} {...props} />
    </div>
  );
}

export function MarkdownTableHead({ className, ...props }: ComponentProps<"thead">) {
  return <thead className={cn("bg-muted/50", className)} {...props} />;
}

export function MarkdownTableRow({ className, ...props }: ComponentProps<"tr">) {
  return <tr className={cn("border-b border-border/60 last:border-0", className)} {...props} />;
}

export function MarkdownTableCell({ className, ...props }: ComponentProps<"td">) {
  return <td className={cn("px-3 py-2 align-top text-foreground", className)} {...props} />;
}

export function MarkdownTableHeaderCell({ className, ...props }: ComponentProps<"th">) {
  return (
    <th
      className={cn("px-3 py-2 text-left text-xs font-semibold text-muted-foreground", className)}
      {...props}
    />
  );
}
