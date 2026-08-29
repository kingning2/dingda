/**
 * 统一空态区块。
 */

import type { ReactNode } from "react";
import { Button } from "@desk/ui";

export interface SectionEmptyProps {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  children?: ReactNode;
}

/** 骨架 / 无数据时的空态。 */
export function SectionEmpty({
  title,
  description,
  actionLabel,
  onAction,
  children,
}: SectionEmptyProps) {
  return (
    <div className="flex flex-col items-start gap-2 py-8">
      <p className="text-[length:var(--text-sm)] font-medium text-foreground">{title}</p>
      {description ? (
        <p className="max-w-lg text-[length:var(--text-sm)] text-muted-foreground">{description}</p>
      ) : null}
      {actionLabel && onAction ? (
        <Button type="button" size="sm" variant="secondary" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
      {children}
    </div>
  );
}
