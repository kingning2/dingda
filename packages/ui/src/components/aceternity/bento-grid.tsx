/**
 * Bento 栅格布局 — Dashboard / Agent 等区块编排。
 *
 * @author agent
 * @created 2026-08-24
 */

import * as React from "react";

import { cn } from "../../lib/cn";

export interface BentoGridProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 列数预设。 */
  columns?: 1 | 2 | 3 | 4 | 5;
}

const COLUMN_CLASS: Record<NonNullable<BentoGridProps["columns"]>, string> = {
  1: "grid-cols-1",
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
  5: "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5",
};

/**
 * Bento 栅格容器。
 */
export function BentoGrid({ columns = 3, className, ...props }: BentoGridProps) {
  return (
    <div
      className={cn(
        "grid auto-rows-[minmax(0,auto)] gap-4",
        COLUMN_CLASS[columns],
        className,
      )}
      {...props}
    />
  );
}
