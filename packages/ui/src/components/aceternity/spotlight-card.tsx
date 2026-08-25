/**
 * 聚光卡片 — GlowingEffect 边框 + 悬停微抬升。
 */

import * as React from "react";
import { motion } from "motion/react";

import { cn } from "../../lib/cn";
import { useReducedMotion } from "../../motion";
import { GlowingEffect } from "../effects/glowing-effect";

export interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  lift?: boolean;
}

export function SpotlightCard({
  className,
  children,
  lift = true,
  ...props
}: SpotlightCardProps) {
  const reducedMotion = useReducedMotion();

  return (
    <div className={cn("group relative rounded-[var(--radius-xl)]", className)} {...props}>
      {!reducedMotion ? (
        <GlowingEffect
          disabled={false}
          spread={36}
          proximity={72}
          inactiveZone={0.15}
          borderWidth={1}
        />
      ) : null}
      <motion.div
        className="relative h-full"
        whileHover={lift && !reducedMotion ? { y: -2 } : undefined}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      >
        {children}
      </motion.div>
    </div>
  );
}
