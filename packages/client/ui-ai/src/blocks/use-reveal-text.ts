/**
 * 流式观感：
 * - live：大块约 2s 化开；小增量跟上
 * - 离开 live：立刻全文（避免思考还在化开时正文已开始）
 * - 历史挂载：立刻全文
 */

import { useEffect, useRef, useState } from "react";

/** 流式内容提交防抖（ms）。 */
export const THINKING_COMMIT_MS = 100;
/** 逐字揭示预算（ms）。 */
export const REVEAL_BUDGET_MS = 1200;
/** Markdown 重解析的绘制间隔；逐字符重绘会导致流式卡顿。 */
const PAINT_INTERVAL_MS = 60;
const SNAP_CHARS = 8;

/** 把高频思考源合并成稳定输入。 */
export function useCoalescedSource(source: string, live: boolean): string {
  const [snapshot, setSnapshot] = useState(source);
  const latestRef = useRef(source);
  const timerRef = useRef<number | null>(null);
  latestRef.current = source;

  useEffect(() => {
    if (!live) {
      if (timerRef.current != null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      setSnapshot(source);
      return;
    }
    if (snapshot === source) return;
    if (timerRef.current != null) return;
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      setSnapshot(latestRef.current);
    }, THINKING_COMMIT_MS);
  }, [live, snapshot, source]);

  useEffect(
    () => () => {
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  return live ? snapshot : source;
}

function budgetFor(pending: number): number {
  return Math.min(REVEAL_BUDGET_MS, Math.max(320, pending * 4));
}

/** 逐字揭示效果：按预算匀速打出文字。 */
export function useRevealText(source: string, live: boolean): string {
  const coalesced = useCoalescedSource(source, live);
  const [visible, setVisible] = useState(() => (live ? "" : source));
  const visibleRef = useRef(visible);
  visibleRef.current = visible;
  const rafRef = useRef<number | null>(null);
  const wasLiveRef = useRef(live);

  useEffect(() => {
    const cancelRaf = () => {
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    const from = visibleRef.current;
    const target = coalesced;

    const wasLive = wasLiveRef.current;
    wasLiveRef.current = live;

    if (!live) {
      cancelRaf();
      const pending = target.length - from.length;
      if (wasLive && pending > 0 && target.startsWith(from)) {
        const started = performance.now();
        const startLen = from.length;
        const budget = Math.min(280, Math.max(120, pending * 4));
        const tick = (now: number) => {
          const progress = Math.min(1, (now - started) / budget);
          const eased = 1 - (1 - progress) ** 2;
          const len = Math.min(
            target.length,
            startLen + Math.max(1, Math.ceil((target.length - startLen) * eased)),
          );
          const next = target.slice(0, len);
          setVisible(next);
          visibleRef.current = next;
          if (len < target.length) rafRef.current = requestAnimationFrame(tick);
          else rafRef.current = null;
        };
        rafRef.current = requestAnimationFrame(tick);
        return () => cancelRaf();
      }
      setVisible(target);
      visibleRef.current = target;
      return;
    }

    if (target === from) {
      cancelRaf();
      return;
    }
    if (from.length > 0 && !target.startsWith(from)) {
      cancelRaf();
      setVisible(target);
      visibleRef.current = target;
      return;
    }
    const pending = target.length - from.length;
    if (pending <= SNAP_CHARS) {
      cancelRaf();
      setVisible(target);
      visibleRef.current = target;
      return;
    }
    if (pending <= 0) {
      cancelRaf();
      setVisible(target);
      visibleRef.current = target;
      return;
    }

    cancelRaf();
    const started = performance.now();
    const startLen = from.length;
    const budget = budgetFor(pending);
    let lastPaint = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - started) / budget);
      const eased = 1 - (1 - progress) ** 2;
      const len = Math.min(
        target.length,
        startLen + Math.max(1, Math.ceil((target.length - startLen) * eased)),
      );
      const final = len >= target.length;

      if (final || now - lastPaint >= PAINT_INTERVAL_MS) {
        lastPaint = now;
        const next = target.slice(0, len);
        setVisible(next);
        visibleRef.current = next;
      }

      if (!final) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        rafRef.current = null;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelRaf();
  }, [coalesced, live]);

  return live ? visible : coalesced;
}
