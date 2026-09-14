/**
 * Markdown 表格：表头、行、单元格的样式封装。
 *
 * 职责：把 `<table>` 包进横向滚动容器，并给表头加 muted 背景、
 * 给行间加分隔线，与正文拉开层级。
 */

import type { ComponentProps } from "react";

import { cn } from "@v2/ui-primitives/utils";

/** 表格容器：横向滚动 + 圆角边框。 */
export function MarkdownTable({ className, ...props }: ComponentProps<"table">) {
  return (
    <div className="my-3 w-full overflow-x-auto rounded-lg border border-border/80">
      <table className={cn("w-full min-w-[480px] border-collapse text-sm", className)} {...props} />
    </div>
  );
}

/** 表头行。 */
export function MarkdownTableHead({ className, ...props }: ComponentProps<"thead">) {
  return <thead className={cn("bg-muted/50", className)} {...props} />;
}

/** 数据行。 */
export function MarkdownTableRow({ className, ...props }: ComponentProps<"tr">) {
  return <tr className={cn("border-b border-border/60 last:border-0", className)} {...props} />;
}

/** 单元格。 */
export function MarkdownTableCell({ className, ...props }: ComponentProps<"td">) {
  return <td className={cn("px-3 py-2 align-top text-foreground", className)} {...props} />;
}

/** 表头单元格。 */
export function MarkdownTableHeaderCell({ className, ...props }: ComponentProps<"th">) {
  return (
    <th
      className={cn("px-3 py-2 text-left text-xs font-semibold text-muted-foreground", className)}
      {...props}
    />
  );
}
