/**
 * CrawlerProgress — 采集进度条 + 计数。
 */

import { motion } from "motion/react";

import { cn } from "../../lib/cn";
import { useReducedMotion } from "../../motion";
import { Progress } from "../progress";

export interface CrawlerProgressCounts {
  crawled?: number;
  matched?: number;
  failed?: number;
}

export interface CrawlerProgressProps {
  label?: string;
  /** 0–100 */
  value: number;
  counts?: CrawlerProgressCounts;
  running?: boolean;
  /** 是否显示右侧百分比数字 */
  showValue?: boolean;
  className?: string;
}

export function CrawlerProgress({
  label = "采集进度",
  value,
  counts,
  running = false,
  showValue = true,
  className,
}: CrawlerProgressProps) {
  const reducedMotion = useReducedMotion();
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div
      className={cn(
        "rounded-[var(--radius-xl)] border border-border/70 bg-card p-4 shadow-sm",
        className,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="font-medium text-foreground">{label}</h3>
        {showValue ? (
          <span className="tabular-nums text-[length:var(--text-sm)] text-muted-foreground">
            {Math.round(clamped)}%
          </span>
        ) : null}
      </div>
      <motion.div
        animate={
          running && !reducedMotion
            ? { opacity: [1, 0.72, 1] }
            : { opacity: 1 }
        }
        transition={
          running && !reducedMotion
            ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" }
            : undefined
        }
      >
        <Progress value={clamped} />
      </motion.div>
      {counts ? (
        <dl className="mt-3 grid grid-cols-3 gap-2 text-center text-[length:var(--text-xs)]">
          <div>
            <dt className="text-muted-foreground">已采集</dt>
            <dd className="mt-0.5 tabular-nums font-medium text-foreground">
              {counts.crawled ?? 0}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">已匹配</dt>
            <dd className="mt-0.5 tabular-nums font-medium text-foreground">
              {counts.matched ?? 0}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">失败</dt>
            <dd className="mt-0.5 tabular-nums font-medium text-foreground">
              {counts.failed ?? 0}
            </dd>
          </div>
        </dl>
      ) : null}
    </div>
  );
}
