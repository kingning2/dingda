import type { CSSProperties } from "react";

import { chatTokens as t } from "./tokens";

export const chatStyles = {
  surface: {
    display: "flex",
    minHeight: 0,
    flex: 1,
    flexDirection: "column",
    overflow: "hidden",
    background: "transparent",
  } satisfies CSSProperties,

  banner: {
    flexShrink: 0,
    borderBottom: `1px solid color-mix(in oklab, ${t.border} 60%, transparent)`,
    padding: "8px 16px",
    color: t.mutedFg,
    fontSize: t.textXs,
    textAlign: "center",
  } satisfies CSSProperties,

  error: {
    flexShrink: 0,
    borderTop: `1px solid color-mix(in oklab, ${t.destructive} 30%, transparent)`,
    background: `color-mix(in oklab, ${t.destructive} 5%, transparent)`,
    padding: "8px 16px",
    color: t.destructive,
    fontSize: t.textXs,
  } satisfies CSSProperties,

  messages: {
    position: "relative",
    minHeight: 0,
    flex: 1,
    overflowY: "auto",
    overscrollBehavior: "contain",
    padding: `16px calc(${t.composerClearance}px + 16px)`,
  } satisfies CSSProperties,

  column: {
    display: "flex",
    width: "100%",
    maxWidth: t.width,
    flexDirection: "column",
    margin: "0 auto",
    gap: t.flowGap,
  } satisfies CSSProperties,

  welcome: {
    display: "flex",
    minHeight: "min(24rem, 50vh)",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "2rem 0",
    color: t.mutedFg,
    fontSize: t.textSm,
  } satisfies CSSProperties,

  userRow: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    gap: 6,
  } satisfies CSSProperties,

  userBubble: {
    maxWidth: `min(calc(${t.width} * 0.702), 82%)`,
    padding: "10px 16px",
    borderRadius: t.bubbleRadius,
    background: t.bubbleBg,
    color: t.fg,
    fontSize: t.textSm,
    lineHeight: 1.57,
    whiteSpace: "pre-wrap",
    overflowWrap: "break-word",
  } satisfies CSSProperties,

  thinking: {
    display: "inline-flex",
    height: 26,
    alignItems: "center",
    fontSize: t.textSm,
    fontWeight: 600,
    lineHeight: "22px",
    whiteSpace: "nowrap",
    background: `linear-gradient(90deg, ${t.primary} 0%, ${t.primary} 40%, color-mix(in oklab, ${t.primary} 35%, transparent) 50%, ${t.primary} 60%, ${t.primary} 100%)`,
    backgroundPosition: "100% 0",
    backgroundSize: "250% 100%",
    backgroundClip: "text",
    color: "transparent",
    WebkitBackgroundClip: "text",
  } satisfies CSSProperties,

  toBottomSlot: {
    position: "sticky",
    bottom: 16,
    zIndex: 2,
    display: "flex",
    height: 0,
    justifyContent: "flex-end",
    paddingRight: `max(0px, calc((100% - ${t.width}) / 2))`,
    pointerEvents: "none",
  } satisfies CSSProperties,

  toBottomBtn: {
    display: "flex",
    width: 34,
    height: 34,
    alignItems: "center",
    justifyContent: "center",
    marginTop: -34,
    padding: 0,
    border: `1px solid color-mix(in oklab, ${t.border} 80%, transparent)`,
    borderRadius: 100,
    background: t.card,
    boxShadow: `0 2px 8px color-mix(in oklab, ${t.fg} 8%, transparent)`,
    color: t.fg,
    cursor: "pointer",
    pointerEvents: "auto",
  } satisfies CSSProperties,

  composer: {
    display: "flex",
    flexShrink: 0,
    flexDirection: "column",
    alignItems: "center",
    padding: `0 ${t.composerClearance}px 8px`,
  } satisfies CSSProperties,

  composerCard: {
    boxSizing: "border-box",
    display: "flex",
    width: "100%",
    maxWidth: `calc(${t.width} + 32px)`,
    flexDirection: "column",
    gap: 12,
    paddingTop: 10,
    border: `1px solid color-mix(in oklab, ${t.border} 90%, transparent)`,
    borderRadius: t.composerRadius,
    background: t.inputSurface,
    boxShadow: `0 2px 12px color-mix(in oklab, ${t.fg} 6%, transparent)`,
    fontSize: t.textSm,
    lineHeight: 1.5,
  } satisfies CSSProperties,

  composerScroll: {
    maxHeight: "14lh",
    overflowY: "auto",
    marginRight: 4,
  } satisfies CSSProperties,

  composerInput: {
    boxSizing: "border-box",
    width: "100%",
    minHeight: 28,
    resize: "none",
    padding: "4px 8px 0 16px",
    border: "none",
    background: "transparent",
    color: t.fg,
    font: "inherit",
    lineHeight: "inherit",
    outline: "none",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
  } satisfies CSSProperties,

  composerRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-end",
    padding: "2px 8px 6px",
  } satisfies CSSProperties,

  composerSend: (disabled: boolean, hovered: boolean): CSSProperties => ({
    display: "grid",
    width: 34,
    height: 34,
    placeItems: "center",
    border: "none",
    borderRadius: 999,
    background: disabled ? t.sendFill : hovered ? t.sendHover : t.sendFill,
    color: t.primaryFg,
    cursor: disabled ? "default" : "pointer",
    transform: "translateY(-2px)",
    transition: "background-color 100ms ease",
    opacity: disabled ? 0.4 : 1,
  }),

  disclaimer: {
    width: "100%",
    maxWidth: `calc(${t.width} + 32px)`,
    marginTop: 8,
    color: t.mutedFg,
    fontSize: t.textXs,
    textAlign: "center",
  } satisfies CSSProperties,

  assistantTurn: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  } satisfies CSSProperties,

  disclosure: {
    display: "flex",
    flexDirection: "column",
  } satisfies CSSProperties,

  disclosureRow: {
    position: "relative",
    display: "flex",
    width: "100%",
    alignItems: "center",
    gap: 6,
    overflow: "hidden",
    padding: "2px 0",
    border: "none",
    background: "none",
    color: "inherit",
    font: "inherit",
    textAlign: "left",
    cursor: "pointer",
  } satisfies CSSProperties,

  disclosureLeading: {
    display: "flex",
    flexShrink: 0,
    color: t.mutedFg,
  } satisfies CSSProperties,

  disclosureTitle: {
    flexShrink: 0,
    fontSize: t.textSm,
    fontWeight: 400,
    color: t.fg,
  } satisfies CSSProperties,

  disclosureSeparator: {
    flex: "none",
    width: 2,
    height: 2,
    margin: "0 8px",
    borderRadius: 1,
    background: t.mutedFg,
  } satisfies CSSProperties,

  disclosureSummary: (followEnd?: boolean): CSSProperties => ({
    minWidth: 0,
    overflow: "hidden",
    flex: "1 1 auto",
    color: t.mutedFg,
    fontSize: t.textXs,
    lineHeight: 1.43,
    textOverflow: followEnd ? "clip" : "ellipsis",
    whiteSpace: "nowrap",
  }),

  disclosureChevron: {
    flexShrink: 0,
    color: t.mutedFg,
  } satisfies CSSProperties,

  disclosureBody: {
    margin: "4px 0 4px 22px",
    padding: "8px 12px",
    border: `1px solid color-mix(in oklab, ${t.border} 80%, transparent)`,
    borderRadius: 12,
    background: `color-mix(in oklab, var(--color-muted) 30%, ${t.card})`,
    color: t.mutedFg,
    fontSize: t.textXs,
    lineHeight: 1.5,
    whiteSpace: "pre-wrap",
    overflowWrap: "break-word",
  } satisfies CSSProperties,

  markdown: {
    minWidth: 0,
    overflowWrap: "anywhere",
    color: t.fg,
    fontSize: t.textSm,
    lineHeight: 1.57,
  } satisfies CSSProperties,

  markdownP: { margin: "12px 0" } satisfies CSSProperties,
  markdownHeading: { margin: "20px 0 12px", fontWeight: 600 } satisfies CSSProperties,
  markdownList: { margin: "12px 0", paddingLeft: "1.25rem" } satisfies CSSProperties,
  markdownLi: { marginTop: 4 } satisfies CSSProperties,
  markdownLink: { color: t.primary, textDecoration: "none" } satisfies CSSProperties,
  markdownCode: {
    padding: "0 5px",
    borderRadius: 6,
    background: "color-mix(in oklab, var(--color-muted) 50%, transparent)",
    fontSize: "0.875em",
  } satisfies CSSProperties,
  markdownPre: {
    margin: "12px 0",
    padding: "12px 16px",
    overflowX: "auto",
    borderRadius: 12,
    background: `color-mix(in oklab, var(--color-muted) 40%, ${t.card})`,
    fontSize: t.textXs,
  } satisfies CSSProperties,
  markdownBlockquote: {
    margin: "12px 0",
    paddingLeft: 14,
    borderLeft: `2px solid ${t.mutedFg}`,
    color: t.mutedFg,
  } satisfies CSSProperties,

  cursor: {
    display: "inline-block",
    width: "0.45ch",
    height: "1em",
    marginLeft: 1,
    background: `color-mix(in oklab, ${t.fg} 70%, transparent)`,
    animation: "pulse 1s ease-in-out infinite",
  } satisfies CSSProperties,

  runFeed: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    width: "100%",
  } satisfies CSSProperties,

  processToggle: (open: boolean): CSSProperties => ({
    boxSizing: "border-box",
    display: "flex",
    alignItems: "center",
    width: "100%",
    minWidth: 0,
    height: 33,
    padding: "0 0 8px",
    marginBottom: open ? 0 : 8,
    border: "none",
    borderBottom: `1px solid color-mix(in oklab, ${t.border} 70%, transparent)`,
    background: "none",
    color: t.mutedFg,
    cursor: "pointer",
    textAlign: "left",
  }),

  processToggleLabel: {
    minWidth: 0,
    overflow: "hidden",
    flex: 1,
    fontSize: t.textSm,
    lineHeight: "24px",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  } satisfies CSSProperties,

  processToggleChevron: (open: boolean): CSSProperties => ({
    flex: "none",
    marginLeft: 6,
    color: t.mutedFg,
    transform: open ? "rotate(0deg)" : "rotate(-90deg)",
    transition: "transform 100ms ease",
  }),

  processPanel: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    paddingBottom: 8,
  } satisfies CSSProperties,

  runFeedStatus: {
    margin: 0,
    color: t.mutedFg,
    fontSize: t.textSm,
  } satisfies CSSProperties,

  runFeedLogs: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    padding: "8px 12px",
    border: `1px solid color-mix(in oklab, ${t.border} 80%, transparent)`,
    borderRadius: 12,
    background: `color-mix(in oklab, var(--color-muted) 25%, ${t.card})`,
  } satisfies CSSProperties,

  runFeedLogLine: (streaming?: boolean): CSSProperties => ({
    margin: 0,
    color: streaming ? t.fg : t.mutedFg,
    fontSize: t.textXs,
    lineHeight: 1.5,
    whiteSpace: "pre-wrap",
    overflowWrap: "break-word",
  }),

  runFeedReply: {
    padding: "4px 0",
  } satisfies CSSProperties,

  runFeedReplyTitle: {
    margin: "0 0 8px",
    fontSize: t.textSm,
    fontWeight: 600,
    color: t.fg,
  } satisfies CSSProperties,

  runFeedReplyBody: {
    margin: 0,
    color: t.fg,
    fontSize: t.textSm,
    lineHeight: 1.57,
    whiteSpace: "pre-wrap",
  } satisfies CSSProperties,

  thinkSection: {
    display: "flex",
    flexDirection: "column",
    gap: 0,
    width: "100%",
  } satisfies CSSProperties,

  thinkHeader: (): CSSProperties => ({
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    width: "100%",
    padding: "8px 0",
    border: "none",
    background: "none",
    color: t.fg,
    cursor: "pointer",
    textAlign: "left",
  }),

  thinkHeaderTitle: {
    fontSize: t.textSm,
    fontWeight: 600,
  } satisfies CSSProperties,

  timeline: {
    display: "flex",
    flexDirection: "column",
    gap: 0,
    padding: "4px 0 8px",
  } satisfies CSSProperties,

  timelineItem: {
    display: "flex",
    gap: 12,
    minHeight: 48,
  } satisfies CSSProperties,

  timelineRail: {
    display: "flex",
    width: 20,
    flexDirection: "column",
    alignItems: "center",
    flexShrink: 0,
  } satisfies CSSProperties,

  timelineDot: (status: "running" | "done" | "error"): CSSProperties => ({
    display: "grid",
    width: 20,
    height: 20,
    placeItems: "center",
    borderRadius: 999,
    background:
      status === "running"
        ? `color-mix(in oklab, ${t.primary} 15%, ${t.card})`
        : status === "error"
          ? `color-mix(in oklab, ${t.destructive} 12%, ${t.card})`
          : `color-mix(in oklab, var(--color-muted) 50%, ${t.card})`,
    border: `1px solid color-mix(in oklab, ${t.border} 80%, transparent)`,
    color: status === "running" ? t.primary : status === "error" ? t.destructive : t.mutedFg,
  }),

  timelineLine: {
    width: 2,
    flex: 1,
    minHeight: 12,
    marginTop: 4,
    background: `color-mix(in oklab, ${t.border} 80%, transparent)`,
  } satisfies CSSProperties,

  timelineContent: {
    minWidth: 0,
    flex: 1,
    paddingBottom: 14,
  } satisfies CSSProperties,

  timelineTitleRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  } satisfies CSSProperties,

  timelineTitle: {
    margin: 0,
    color: t.fg,
    fontSize: t.textSm,
    fontWeight: 500,
  } satisfies CSSProperties,

  timelineStatus: (running?: boolean): CSSProperties => ({
    flexShrink: 0,
    color: running ? t.primary : t.mutedFg,
    fontSize: "11px",
  }),

  timelineSummary: {
    margin: "4px 0 0",
    color: t.mutedFg,
    fontSize: t.textXs,
    lineHeight: 1.45,
  } satisfies CSSProperties,

  timelineDetail: {
    marginTop: 8,
    padding: "8px 10px",
    border: `1px solid color-mix(in oklab, ${t.border} 70%, transparent)`,
    borderRadius: 10,
    background: `color-mix(in oklab, var(--color-muted) 25%, ${t.card})`,
    fontSize: t.textXs,
  } satisfies CSSProperties,

  runFeedComplete: {
    marginTop: 4,
    padding: "8px 12px",
    borderRadius: 10,
    background: `color-mix(in oklab, var(--color-muted) 35%, ${t.card})`,
    color: t.mutedFg,
    fontSize: t.textXs,
    lineHeight: 1.45,
  } satisfies CSSProperties,
} as const;
