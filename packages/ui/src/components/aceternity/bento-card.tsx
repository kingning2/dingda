/**
 * Bento 卡片 — 跨列 span + 可选光晕。
 *
 * @author agent
 * @created 2026-08-24
 */

import * as React from "react";
import { motion } from "motion/react";

import { cn } from "../../lib/cn";
import { useReducedMotion } from "../../motion";
import { GlowingEffect } from "../effects/glowing-effect";

export interface BentoCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 跨列数（lg 断点）。 */
  colSpan?: 1 | 2 | 3;
  /** 跨行数。 */
  rowSpan?: 1 | 2;
  /** 是否启用 hover 光晕。 */
  glow?: boolean;
  /** 是否启用 hover 微抬升。 */
  lift?: boolean;
}

const COL_SPAN: Record<NonNullable<BentoCardProps["colSpan"]>, string> = {
  1: "",
  2: "lg:col-span-2",
  3: "lg:col-span-3",
};

const ROW_SPAN: Record<NonNullable<BentoCardProps["rowSpan"]>, string> = {
  1: "",
  2: "row-span-2",
};

/**
 * Bento 布局单元卡片。
 */
export function BentoCard({
  colSpan = 1,
  rowSpan = 1,
  glow = false,
  lift = true,
  className,
  children,
  ...props
}: BentoCardProps) {
  const reducedMotion = useReducedMotion();

  return (
    <div
      className={cn(
        "group relative rounded-[var(--radius-xl)] border border-border/70 bg-card/80 backdrop-blur-sm",
        COL_SPAN[colSpan],
        ROW_SPAN[rowSpan],
        className,
      )}
      {...props}
    >
      {glow && !reducedMotion ? (
        <GlowingEffect
          disabled={false}
          spread={32}
          proximity={80}
          inactiveZone={0.12}
          borderWidth={1}
        />
      ) : null}
      <motion.div
        className="relative h-full p-5"
        whileHover={lift && !reducedMotion ? { y: -1 } : undefined}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.div>
    </div>
  );
}
