/**
 * Codex TUI 风格活动指示符。
 *
 * 官方 TUI 使用带扫光的 `•`，不依赖额外图形；
 * 保留 ThinkingOrb 名称是为了兼容现有调用。
 */

import { cn } from "@v2/ui-primitives/utils";

/** Codex 活动指示器：旋转的彩色圆点。 */
export function CodexActivityIndicator({ className }: { className?: string }) {
  return (
    <span
      role="img"
      aria-label="Working"
      className={cn("codex-status-shimmer inline-block leading-none", className)}
    >
      •
    </span>
  );
}

/** ThinkingOrb 组件映射表（按平台）。 */
export const ThinkingOrb = CodexActivityIndicator;
