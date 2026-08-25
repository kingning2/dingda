/**
 * 成功揭示 — ready 状态下替换表单内容的最终展示。
 *
 * 纯展示组件，一次性入场动画。
 *
 * @author coisini
 * @created 2026-08-24
 */

import { motion, useReducedMotion } from "@desk/ui";

export interface SuccessRevealProps {
  /** 产品名（来自 LicenseStatus，可能为空）。 */
  product?: string | null;
}

/**
 * 授权成功后的最终内容块。
 *
 * @author coisini
 * @created 2026-08-24
 *
 * @param props.product - 产品名
 */
export function SuccessReveal({ product }: SuccessRevealProps) {
  const reducedMotion = useReducedMotion();
  const ease = [0.16, 1, 0.3, 1] as const;

  return (
    <div className="flex flex-col items-center gap-1 text-center">
      <motion.p
        initial={reducedMotion ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: reducedMotion ? 0 : 0.15, ease }}
        className="text-[length:var(--text-xs)] font-medium uppercase tracking-[0.2em] text-primary"
      >
        LICENSE VERIFIED
      </motion.p>
      <motion.h2
        initial={reducedMotion ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: reducedMotion ? 0 : 0.25, ease }}
        className="text-[length:var(--text-lg)] font-semibold tracking-tight text-foreground"
      >
        {product?.trim() || "DingDa"}
      </motion.h2>
      <motion.p
        initial={reducedMotion ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: reducedMotion ? 0 : 0.35, ease }}
        className="text-[length:var(--text-sm)] text-muted-foreground"
      >
        你的工作区已就绪。
      </motion.p>
    </div>
  );
}
