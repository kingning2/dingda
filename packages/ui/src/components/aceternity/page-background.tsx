/**
 * 页面级 Aceternity 背景 — 聚光灯 / 极光，支持 reduced-motion 降级。
 *
 * @author agent
 * @created 2026-08-24
 */

import { motion } from "motion/react";

import { cn } from "../../lib/cn";
import { useReducedMotion } from "../../motion";
import { AmbientSpotlight } from "../effects/ambient-spotlight";

export type PageBackgroundVariant = "spotlight" | "aurora" | "none";

export interface PageBackgroundProps {
  variant?: PageBackgroundVariant;
  className?: string;
}

function AuroraBackground({ className }: { className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 1.2 }}
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      aria-hidden
    >
      <motion.div
        animate={{
          opacity: [0.35, 0.55, 0.35],
          scale: [1, 1.04, 1],
        }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
        className="absolute -top-1/3 left-1/4 h-[70%] w-[60%] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle, oklch(0.62 0.19 285 / 0.14) 0%, oklch(0.55 0.2 280 / 0.04) 50%, transparent 70%)",
        }}
      />
      <motion.div
        animate={{
          opacity: [0.25, 0.45, 0.25],
          x: [0, 40, 0],
        }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
        className="absolute -right-1/4 top-0 h-[60%] w-[50%] rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle, oklch(0.7 0.15 300 / 0.1) 0%, oklch(0.55 0.2 280 / 0.03) 60%, transparent 80%)",
        }}
      />
    </motion.div>
  );
}

/**
 * 页面环境背景 — 用于 Dashboard / AI / Agent 等入口页。
 */
export function PageBackground({ variant = "spotlight", className }: PageBackgroundProps) {
  const reducedMotion = useReducedMotion();

  if (variant === "none" || reducedMotion) {
    return null;
  }

  if (variant === "aurora") {
    return <AuroraBackground className={className} />;
  }

  return <AmbientSpotlight className={className} />;
}
