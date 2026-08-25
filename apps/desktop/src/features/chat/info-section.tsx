import { type ReactNode } from "react";
import { cn } from "@desk/ui";
import { type LucideIcon } from "@desk/ui/icons";

/** 客户信息区块 — 克制边框卡片（inbox-1 风格）。 */
export function InfoSection({
  icon: Icon,
  title,
  children,
}: {
  icon: LucideIcon;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[var(--radius-lg)] border border-border/80 bg-card p-4">
      <div className="flex items-center gap-2 text-[length:var(--text-sm)] font-medium text-foreground">
        <Icon className="size-4 text-muted-foreground" aria-hidden />
        <span>{title}</span>
      </div>
      <div className="mt-3 space-y-2">{children}</div>
    </section>
  );
}

/** 信息行 — 左标签右值。 */
export function InfoRow({
  label,
  value,
  mono,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-3 text-[length:var(--text-xs)]">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className={cn("min-w-0 break-all text-right text-foreground", mono && "font-mono")}>
        {value || "—"}
      </span>
    </div>
  );
}
