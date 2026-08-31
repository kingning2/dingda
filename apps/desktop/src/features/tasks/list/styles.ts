/**
 * 历史侧栏样式。
 */

import type { CSSProperties } from "react";

import { chatTokens as t } from "../chat/tokens";

export const historyStyles = {
  aside: {
    display: "flex",
    width: 280,
    minWidth: 280,
    height: "100%",
    minHeight: 0,
    flexShrink: 0,
    flexDirection: "column",
    borderRight: `1px solid color-mix(in oklab, ${t.border} 60%, transparent)`,
    background: "var(--color-workspace, var(--color-background))",
  } satisfies CSSProperties,

  header: {
    display: "flex",
    flexShrink: 0,
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    padding: "14px 14px 10px",
  } satisfies CSSProperties,

  brand: {
    margin: 0,
    color: t.fg,
    fontSize: t.textSm,
    fontWeight: 600,
  } satisfies CSSProperties,

  searchWrap: {
    position: "relative",
    flexShrink: 0,
    padding: "0 12px 10px",
  } satisfies CSSProperties,

  searchIcon: {
    position: "absolute",
    top: 9,
    left: 22,
    color: t.mutedFg,
    pointerEvents: "none",
  } satisfies CSSProperties,

  list: {
    minHeight: 0,
    flex: 1,
    overflowY: "auto",
    padding: "0 8px",
  } satisfies CSSProperties,

  empty: {
    margin: 0,
    padding: "24px 8px",
    color: t.mutedFg,
    fontSize: t.textXs,
    textAlign: "center",
  } satisfies CSSProperties,

  group: {
    marginBottom: 12,
  } satisfies CSSProperties,

  groupLabel: {
    margin: "0 0 6px",
    padding: "0 6px",
    color: t.mutedFg,
    fontSize: t.textXs,
    fontWeight: 500,
  } satisfies CSSProperties,

  groupList: {
    margin: 0,
    padding: 0,
    listStyle: "none",
  } satisfies CSSProperties,

  item: (active: boolean): CSSProperties => ({
    display: "block",
    width: "100%",
    padding: "10px 10px",
    border: "none",
    borderRadius: 10,
    background: active
      ? `color-mix(in oklab, ${t.primary} 12%, transparent)`
      : "transparent",
    color: t.fg,
    cursor: "pointer",
    textAlign: "left",
    transition: "background-color 120ms ease",
  }),

  itemTitle: {
    margin: 0,
    overflow: "hidden",
    fontSize: t.textXs,
    fontWeight: 500,
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  } satisfies CSSProperties,

  itemMeta: {
    margin: "4px 0 0",
    overflow: "hidden",
    color: t.mutedFg,
    fontSize: "11px",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  } satisfies CSSProperties,

  itemTime: {
    margin: "2px 0 0",
    color: `color-mix(in oklab, ${t.mutedFg} 80%, transparent)`,
    fontSize: "11px",
  } satisfies CSSProperties,

  footer: {
    flexShrink: 0,
    padding: "10px 12px 14px",
    borderTop: `1px solid color-mix(in oklab, ${t.border} 60%, transparent)`,
  } satisfies CSSProperties,
} as const;
