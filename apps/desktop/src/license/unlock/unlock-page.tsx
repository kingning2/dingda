/**
 * License 解锁页 — 沉浸式激活流程（Locked → Verifying → Unlocking → Ready）。
 *
 * 授权刷新后由既有闸门（AccessGate / UnauthorizedPage）导航回工作区。
 *
 * @author coisini
 * @created 2026-08-24
 */

import { useCallback, useState } from "react";
import { AmbientSpotlight, motion, useReducedMotion } from "@desk/ui";

import { useLicenseGateContext } from "../license-gate-context";
import { UnlockFlow } from "./unlock-flow";

/**
 * 全屏解锁页。
 *
 * @author coisini
 * @created 2026-08-24
 */
export interface UnlockPageProps {
  /** 内嵌在工作区时为 true，不使用全屏高度。 */
  inline?: boolean;
}

export function UnlockPage({ inline }: UnlockPageProps) {
  const reducedMotion = useReducedMotion();
  const { refresh } = useLicenseGateContext();
  const [leaving, setLeaving] = useState(false);

  const handleEnter = useCallback(() => {
    setLeaving(true);
    window.setTimeout(() => refresh(), reducedMotion ? 80 : 380);
  }, [refresh, reducedMotion]);

  return (
    <motion.div
      animate={leaving ? { opacity: 0, scale: reducedMotion ? 1 : 1.03 } : undefined}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className={
        inline
          ? "relative flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-shell px-6"
          : "relative flex h-screen w-full items-center justify-center overflow-hidden bg-shell px-6"
      }
    >
      <AmbientSpotlight className="opacity-70" />
      <div className="relative z-10 flex w-full justify-center">
        <UnlockFlow onEnter={handleEnter} />
      </div>
    </motion.div>
  );
}
