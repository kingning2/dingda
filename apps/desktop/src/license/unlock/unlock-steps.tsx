/**
 * 解锁校验步骤列表 — done / active / pending 三态。
 *
 * @author coisini
 * @created 2026-08-24
 */

import { motion, useReducedMotion } from "@desk/ui";
import { Check } from "@desk/ui/icons";
import { cn } from "@desk/ui";

import type { UnlockStep } from "./types";

export interface UnlockStepsProps {
  steps: UnlockStep[];
}

/**
 * 垂直步骤列表。
 *
 * @author coisini
 * @created 2026-08-24
 *
 * @param props.steps - 当前步骤状态数组
 */
export function UnlockSteps({ steps }: UnlockStepsProps) {
  const reducedMotion = useReducedMotion();

  return (
    <ul className="flex w-full max-w-xs flex-col gap-2.5" aria-live="polite">
      {steps.map((step) => (
        <li
          key={step.id}
          className={cn(
            "flex items-center gap-2.5 text-[length:var(--text-sm)] transition-opacity duration-300",
            step.state === "pending" && "opacity-40",
            step.state === "active" && "text-foreground",
            step.state === "done" && "text-muted-foreground",
          )}
        >
          <span
            className={cn(
              "flex size-4 shrink-0 items-center justify-center rounded-full border transition-colors duration-300",
              step.state === "done" && "border-primary/40 bg-primary/15 text-primary",
              step.state === "active" &&
                "border-primary/50 text-primary",
              step.state === "pending" && "border-border text-transparent",
            )}
          >
            {step.state === "done" ? (
              <motion.span
                initial={reducedMotion ? false : { scale: 0.5, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                className="flex"
              >
                <Check className="size-2.5" strokeWidth={3} />
              </motion.span>
            ) : null}
            {step.state === "active" ? (
              <span className="size-1.5 rounded-full bg-primary motion-safe:animate-pulse" />
            ) : null}
          </span>
          <span>{step.label}</span>
        </li>
      ))}
    </ul>
  );
}
