/**
 * 动画 KPI 统计卡 — Dashboard 核心指标展示。
 *
 * @author agent
 * @created 2026-08-24
 */

import * as React from "react";
import { motion } from "motion/react";
import type { LucideIcon } from "lucide-react";

import { cn } from "../../lib/cn";
import { useReducedMotion } from "../../motion";
import { GlowingEffect } from "../effects/glowing-effect";

export interface AnimatedStatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: React.ReactNode;
  icon: LucideIcon;
  iconClassName?: string;
  /** 可选副文案（趋势、说明）。 */
  hint?: React.ReactNode;
  /** 点击跳转等。 */
  onAction?: () => void;
}

/**
 * Dashboard KPI 卡片 — 数字入场 + 鼠标跟随光晕。
 */
export function AnimatedStatCard({
  label,
  value,
  icon: Icon,
  iconClassName,
  hint,
  onAction,
  className,
  ...props
}: AnimatedStatCardProps) {
  const reducedMotion = useReducedMotion();
  const interactive = Boolean(onAction);

  const body = (
    <>
      {!reducedMotion ? (
        <GlowingEffect
          disabled={false}
          spread={28}
          proximity={64}
          inactiveZone={0.2}
          borderWidth={1}
        />
      ) : null}
      <div className="relative flex items-center gap-3 p-5">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-[var(--radius-lg)] bg-muted/80 transition-colors group-hover:bg-muted">
          <Icon className={cn("size-5", iconClassName)} aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[length:var(--text-xs)] text-muted-foreground">{label}</p>
          <motion.p
            key={String(value)}
            initial={reducedMotion ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="text-[length:var(--text-2xl)] font-semibold tabular-nums text-foreground"
          >
            {value}
          </motion.p>
          {hint ? (
            <p className="mt-0.5 text-[length:var(--text-xs)] text-muted-foreground">{hint}</p>
          ) : null}
        </div>
      </div>
    </>
  );

  const cardClass = cn(
    "group relative overflow-hidden rounded-[var(--radius-xl)] border border-border/70 bg-card/80 backdrop-blur-sm",
    interactive && "cursor-pointer transition-colors hover:bg-card",
    className,
  );

  if (interactive) {
    return (
      <button
        type="button"
        className={cn("text-left", cardClass)}
        onClick={onAction}
      >
        {body}
      </button>
    );
  }

  return (
    <div className={cardClass} {...props}>
      {body}
    </div>
  );
}
