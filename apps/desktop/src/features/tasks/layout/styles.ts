/**
 * 页面级布局样式 — 三栏任务中心。
 */

import type { CSSProperties } from "react";

import { chatTokens as t } from "../chat/tokens";

export const pageStyles = {
  shell: {
    display: "flex",
    height: "100%",
    minHeight: 0,
    flex: 1,
    overflow: "hidden",
    background: t.bg,
  } satisfies CSSProperties,

  chatColumn: {
    display: "flex",
    minWidth: 0,
    flex: 1,
    flexDirection: "column",
    overflow: "hidden",
    borderRight: `1px solid color-mix(in oklab, ${t.border} 60%, transparent)`,
  } satisfies CSSProperties,

  chatHeader: {
    display: "flex",
    flexShrink: 0,
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    padding: "12px 20px",
    borderBottom: `1px solid color-mix(in oklab, ${t.border} 60%, transparent)`,
  } satisfies CSSProperties,

  chatTitle: {
    margin: 0,
    minWidth: 0,
    overflow: "hidden",
    flex: 1,
    color: t.fg,
    fontSize: t.textSm,
    fontWeight: 600,
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  } satisfies CSSProperties,

  chatSubtitle: {
    margin: "2px 0 0",
    color: t.mutedFg,
    fontSize: t.textXs,
  } satisfies CSSProperties,
} as const;
