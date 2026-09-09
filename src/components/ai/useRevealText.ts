/**
 * 流式观感：
 * - live：大块约 2s 化开；小增量跟上
 * - 离开 live：立刻全文（避免思考还在化开时正文已开始）
 * - 历史挂载：立刻全文
 */

import { useEffect, useRef, useState } from "react";

export const THINKING_COMMIT_MS = 80;
export const REVEAL_BUDGET_MS = 2200;
const SNAP_CHARS = 8;

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
  return Math.min(REVEAL_BUDGET_MS, Math.max(350, Math.ceil(pending / 90) * 1000));
}

export function useRevealText(source: string, live: boolean): string {
  const coalesced = useCoalescedSource(source, live);
  const [visible, setVisible] = useState(() => (live ? "" : source));
  const visibleRef = useRef(visible);
  visibleRef.current = visible;
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const cancelRaf = () => {
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };

    const from = visibleRef.current;
    const target = coalesced;

    if (!live) {
      cancelRaf();
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
    const tick = (now: number) => {
      const t = Math.min(1, (now - started) / budget);
      const eased = 1 - (1 - t) ** 2;
      const len = Math.min(
        target.length,
        startLen + Math.max(1, Math.ceil((target.length - startLen) * eased)),
      );
      const next = target.slice(0, len);
      setVisible(next);
      visibleRef.current = next;
      if (len < target.length) {
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
