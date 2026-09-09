/**
 * 内层滚动框贴底跟随（对齐 OpenDesign useThinkingFollow）。
 */

import { useEffect, type RefObject } from "react";
import { nextFollowIntent, type FollowIntent, type ScrollSample } from "./stick-to-bottom";

export function useThinkingFollow(ref: RefObject<HTMLElement | null>, active: boolean): void {
  useEffect(() => {
    const box = ref.current;
    if (!box || !active) return;

    let intent: FollowIntent = { following: true, escaped: false };
    const sample = (): ScrollSample => ({
      scrollTop: box.scrollTop,
      scrollHeight: box.scrollHeight,
      clientHeight: box.clientHeight,
    });
    let last = sample();

    const stick = () => {
      const max = box.scrollHeight - box.clientHeight;
      if (max <= 0) return;
      if (box.scrollTop !== max) box.scrollTop = max;
    };

    const onGeometry = () => {
      if (intent.following) stick();
      last = sample();
    };

    const onScroll = () => {
      const next = sample();
      intent = nextFollowIntent(intent, last, next);
      last = next;
    };
    box.addEventListener("scroll", onScroll, { passive: true });

    const fold = box.closest("details");
    const onToggle = () => {
      if (!fold?.open) return;
      intent = { following: true, escaped: false };
      stick();
      last = sample();
    };
    fold?.addEventListener("toggle", onToggle);

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(onGeometry);
      observer.observe(box);
    }
    let mutations: MutationObserver | null = null;
    if (typeof MutationObserver !== "undefined") {
      mutations = new MutationObserver(onGeometry);
      mutations.observe(box, { childList: true, subtree: true, characterData: true });
    }
    onGeometry();

    return () => {
      box.removeEventListener("scroll", onScroll);
      fold?.removeEventListener("toggle", onToggle);
      observer?.disconnect();
      mutations?.disconnect();
    };
  }, [ref, active]);
}
