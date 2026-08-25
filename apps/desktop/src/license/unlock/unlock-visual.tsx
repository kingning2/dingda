/**
 * 解锁页中央视觉：Logo 圆环 + 状态驱动的光晕与图标。
 *
 * 纯展示组件 — 只根据 status 渲染，不含业务逻辑。
 *
 * @author coisini
 * @created 2026-08-24
 */

import { AnimatePresence, motion, useReducedMotion } from "@desk/ui";
import { Lock, LockOpen } from "@desk/ui/icons";
import { cn } from "@desk/ui";

import type { UnlockStatus } from "./types";

export interface UnlockVisualProps {
  status: UnlockStatus;
}

const unlocked = (status: UnlockStatus) => status === "unlocking" || status === "ready";

/**
 * 中央解锁视觉。
 *
 * @author coisini
 * @created 2026-08-24
 *
 * @param props.status - 当前流程状态
 */
export function UnlockVisual({ status }: UnlockVisualProps) {
  const reducedMotion = useReducedMotion();
  const isUnlocked = unlocked(status);
  const isError = status === "error";
  const busy = status === "verifying" || status === "unlocking";

  return (
    <div className="relative flex size-24 items-center justify-center">
      {/* 静态底环 */}
      <div
        className={cn(
          "absolute inset-0 rounded-full border border-border bg-card/60 shadow-sm transition-colors duration-300",
          isUnlocked && "border-primary/30",
        )}
      />

      {/* 进度环：verifying / unlocking 时旋转（transform 动画，低开销） */}
      {busy ? (
        <div
          className="absolute inset-0 rounded-full border border-transparent border-t-primary/70 border-r-primary/40 motion-safe:animate-[spin_1.4s_linear_infinite]"
          aria-hidden
        />
      ) : null}

      {/* 成功外扩光环（一次性） */}
      <AnimatePresence>
        {isUnlocked && !reducedMotion ? (
          <motion.div
            key="reveal-ring"
            initial={{ scale: 0.9, opacity: 0.5 }}
            animate={{ scale: 1.45, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
            className="absolute inset-0 rounded-full border border-primary/50"
            aria-hidden
          />
        ) : null}
      </AnimatePresence>

      {/* 呼吸光晕：仅 busy 时存在，一次性状态期 */}
      <AnimatePresence>
        {busy ? (
          <motion.div
            key="busy-glow"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.5, 0.25] }}
            transition={{ duration: 1.2 }}
            className="absolute -inset-3 rounded-full bg-primary/20 blur-xl"
            aria-hidden
          />
        ) : null}
      </AnimatePresence>

      {/* 图标 */}
      <div
        className={cn(
          "relative flex items-center justify-center transition-colors duration-300",
          isUnlocked ? "text-primary" : isError ? "text-muted-foreground" : "text-foreground",
        )}
      >
        <AnimatePresence mode="wait" initial={false}>
          {isUnlocked ? (
            <motion.span
              key="unlocked"
              initial={{ scale: reducedMotion ? 1 : 0.7, opacity: 0, rotate: -12 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <LockOpen className="size-8" strokeWidth={1.5} />
            </motion.span>
          ) : (
            <motion.span
              key="locked"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1, y: busy ? [0, -2, 0] : 0 }}
              exit={{ opacity: 0 }}
              transition={
                busy ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" } : { duration: 0.2 }
              }
            >
              <Lock className="size-8" strokeWidth={1.5} />
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
