/** 聊天区设计令牌 — 映射 desk 语义变量，供 styles.ts 引用。 */

export const chatTokens = {
  width: "42rem",
  flowGap: 16,
  composerClearance: 16,
  bubbleRadius: 22,
  composerRadius: 22,
  bubbleBg: "color-mix(in oklab, var(--color-muted) 55%, var(--color-card))",
  inputSurface: "var(--color-card)",
  sendFill: "var(--color-primary)",
  sendHover: "color-mix(in oklab, var(--color-primary) 88%, white)",
  textSm: "var(--text-sm)",
  textXs: "var(--text-xs)",
  fg: "var(--color-foreground)",
  mutedFg: "var(--color-muted-foreground)",
  primary: "var(--color-primary)",
  primaryFg: "var(--color-primary-foreground)",
  card: "var(--color-card)",
  border: "var(--color-border)",
  destructive: "var(--color-destructive)",
  bg: "var(--color-background)",
} as const;
