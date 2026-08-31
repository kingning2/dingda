/**
 * 右侧分析面板样式。
 */

import type { CSSProperties } from "react";

import { chatTokens as t } from "../chat/tokens";

export const resultsStyles = {
  aside: {
    display: "flex",
    width: "min(420px, 36vw)",
    minWidth: 320,
    height: "100%",
    minHeight: 0,
    flexShrink: 0,
    flexDirection: "column",
    overflow: "hidden",
    background: t.card,
  } satisfies CSSProperties,

  header: {
    flexShrink: 0,
    padding: "14px 16px 10px",
    borderBottom: `1px solid color-mix(in oklab, ${t.border} 60%, transparent)`,
  } satisfies CSSProperties,

  headerTitle: {
    margin: 0,
    color: t.fg,
    fontSize: t.textSm,
    fontWeight: 600,
  } satisfies CSSProperties,

  headerMeta: {
    margin: "4px 0 0",
    color: t.mutedFg,
    fontSize: t.textXs,
  } satisfies CSSProperties,

  tabs: {
    display: "flex",
    flexShrink: 0,
    gap: 4,
    overflowX: "auto",
    padding: "0 12px",
    borderBottom: `1px solid color-mix(in oklab, ${t.border} 60%, transparent)`,
  } satisfies CSSProperties,

  tab: (active: boolean): CSSProperties => ({
    flexShrink: 0,
    padding: "10px 10px",
    border: "none",
    borderBottom: active ? `2px solid ${t.primary}` : "2px solid transparent",
    background: "none",
    color: active ? t.fg : t.mutedFg,
    fontSize: t.textXs,
    fontWeight: active ? 600 : 400,
    cursor: "pointer",
  }),

  body: {
    minHeight: 0,
    flex: 1,
    overflowY: "auto",
    padding: 12,
  } satisfies CSSProperties,

  section: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
  } satisfies CSSProperties,

  card: {
    padding: "12px 14px",
    border: `1px solid color-mix(in oklab, ${t.border} 70%, transparent)`,
    borderRadius: 12,
    background: `color-mix(in oklab, var(--color-muted) 20%, ${t.card})`,
  } satisfies CSSProperties,

  cardTitle: {
    margin: "0 0 8px",
    color: t.fg,
    fontSize: t.textXs,
    fontWeight: 600,
  } satisfies CSSProperties,

  cardBody: {
    margin: 0,
    color: t.fg,
    fontSize: t.textXs,
    lineHeight: 1.55,
    whiteSpace: "pre-wrap",
  } satisfies CSSProperties,

  sourceList: {
    margin: 0,
    padding: 0,
    listStyle: "none",
  } satisfies CSSProperties,

  sourceItem: {
    marginTop: 6,
    fontSize: t.textXs,
    lineHeight: 1.45,
    color: t.mutedFg,
  } satisfies CSSProperties,

  sourceLink: {
    color: t.primary,
    textDecoration: "none",
  } satisfies CSSProperties,

  productGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
    gap: 10,
  } satisfies CSSProperties,

  productCard: {
    padding: "10px 12px",
    border: `1px solid color-mix(in oklab, ${t.border} 70%, transparent)`,
    borderRadius: 12,
    background: `color-mix(in oklab, var(--color-muted) 15%, ${t.card})`,
  } satisfies CSSProperties,

  productPlatform: {
    margin: 0,
    color: t.mutedFg,
    fontSize: "11px",
  } satisfies CSSProperties,

  productTitle: {
    margin: "6px 0 0",
    color: t.fg,
    fontSize: t.textXs,
    fontWeight: 500,
    lineHeight: 1.4,
  } satisfies CSSProperties,

  productPrice: {
    margin: "6px 0 0",
    color: t.primary,
    fontSize: t.textSm,
    fontWeight: 600,
  } satisfies CSSProperties,

  productSnippet: {
    margin: "4px 0 0",
    color: t.mutedFg,
    fontSize: "11px",
    lineHeight: 1.4,
  } satisfies CSSProperties,

  placeholder: {
    margin: 0,
    padding: "24px 8px",
    color: t.mutedFg,
    fontSize: t.textXs,
    textAlign: "center",
  } satisfies CSSProperties,

  empty: {
    display: "flex",
    height: "100%",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    textAlign: "center",
  } satisfies CSSProperties,

  emptyTitle: {
    margin: "0 0 8px",
    color: t.fg,
    fontSize: t.textSm,
    fontWeight: 600,
  } satisfies CSSProperties,

  emptyText: {
    margin: 0,
    color: t.mutedFg,
    fontSize: t.textXs,
    lineHeight: 1.5,
  } satisfies CSSProperties,
} as const;
