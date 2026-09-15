/**
 * 聊天记录的滚动行为：sticky 用户消息 + 是否跟随底部。
 *
 * 职责：
 *   从「当前滚到第几轮」推导出 sticky 分区索引与是否吸顶，并维护「用户是否仍在跟随底部」。
 *
 * 设计说明：
 *   - 抽成 hook 而不是留在 Chat 里：这部分只跟滚动数学有关，不表达聊天记录本身，
 *     混在组件里会让「记录怎么渲染」和「滚到哪里」互相干扰阅读。
 *   - `syncStickyAndFollow` 同时挂在 scroll 事件与内容指纹变化上：内容变长时
 *     sticky 索引也要跟着重算，不能只等用户滚动。
 *   - 判断「是否贴底」用 `stick-to-bottom.ts` 的纯函数。注意 Virtualizer 自带
 *     `isAtEnd()` / `getDistanceFromEnd()`，可能可以取代它 —— 属另一轮的核对项，
 *     本轮不动，避免同时改两处行为。
 */

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type { Virtualizer } from "@tanstack/react-virtual";
import { nearBottom, nextFollowIntent, type FollowIntent, type ScrollSample } from "./stick-to-bottom";
import type { ChatTurn } from "./types";

function readScrollSample(el: HTMLElement): ScrollSample {
  return {
    scrollTop: el.scrollTop,
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
  };
}

/** sticky 与跟随底部的配置项。 */
export interface StickyAndFollowOptions {
  scrollRef: RefObject<HTMLDivElement | null>;
  /** 用 `Virtualizer<HTMLDivElement, Element>` 而非 HTMLDivElement：
   *  `useVirtualizer` 的项元素类型就是 `Element`，收窄成 HTMLDivElement 反而不兼容。 */
  virtualizer: Virtualizer<HTMLDivElement, Element>;
  turns: ChatTurn[];
  /** 内容指纹：变化时重算 sticky 索引并触发跟随。 */
  fingerprint: number;
  /** 是否处于活回合。 */
  busy: boolean;
  /** 虚拟行数（含错误尾行）。 */
  rowCount: number;
}

/** sticky 与跟随底部的返回值。 */
export interface StickyAndFollow {
  /** 当前吸顶的那一轮在 turns 里的下标。 */
  stickyIndex: number;
  /** 是否已经滚过该轮顶部（决定要不要显示 sticky 覆盖层）。 */
  stickyPinned: boolean;
  /** 若仍在跟随底部，把最后一轮滚进视野。输入框活动时调用。 */
  keepFollowingToEnd: () => void;
}

/** 虚拟滚动下的 sticky 索引与跟随底部逻辑。 */
export function useStickyAndFollow({
  scrollRef,
  virtualizer,
  turns,
  fingerprint,
  busy,
  rowCount,
}: StickyAndFollowOptions): StickyAndFollow {
  const followRef = useRef<FollowIntent>({ following: true, escaped: false });
  const lastSampleRef = useRef<ScrollSample | null>(null);
  const [stickyIndex, setStickyIndex] = useState(0);
  const [stickyPinned, setStickyPinned] = useState(false);

  const syncStickyAndFollow = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const sample = readScrollSample(el);
    const prev = lastSampleRef.current ?? sample;
    const next = nextFollowIntent(followRef.current, prev, sample);
    followRef.current = next;
    lastSampleRef.current = sample;
    // 用户自己滚回底部时，解除「已脱离跟随」，重新开始跟随。
    if (nearBottom(sample) && !next.escaped) {
      followRef.current = { following: true, escaped: false };
    }

    // 找出最后一个「顶部不超过当前视口顶部」的轮次 —— 它就是当前吸顶的那一轮。
    let active = 0;
    for (let i = 0; i < turns.length; i++) {
      const start = virtualizer.getOffsetForIndex(i, "start");
      if (start == null) continue;
      if (start[0] <= sample.scrollTop + 8) active = i;
    }
    setStickyIndex(active);

    const activeStart = virtualizer.getOffsetForIndex(active, "start");
    const pinned = activeStart != null && sample.scrollTop > activeStart[0] + 4;
    setStickyPinned(pinned);
  }, [scrollRef, turns.length, virtualizer]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    syncStickyAndFollow();
    el.addEventListener("scroll", syncStickyAndFollow, { passive: true });
    return () => el.removeEventListener("scroll", syncStickyAndFollow);
  }, [scrollRef, syncStickyAndFollow]);

  // 内容变长（指纹变）时也要重算 —— 新块进来会改变各轮的高度与偏移。
  useEffect(() => {
    syncStickyAndFollow();
  }, [fingerprint, virtualizer.getTotalSize(), syncStickyAndFollow]);

  // 跟随底部：内容变化且用户没有主动脱离时，把最后一轮滚进视野。
  useEffect(() => {
    if (!followRef.current.following) return;
    if (rowCount === 0) return;
    const frame = window.requestAnimationFrame(() => {
      virtualizer.scrollToIndex(rowCount - 1, { align: "end" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [fingerprint, busy, rowCount, virtualizer]);

  const keepFollowingToEnd = useCallback(() => {
    if (!followRef.current.following) return;
    window.requestAnimationFrame(() => {
      virtualizer.scrollToIndex(Math.max(0, rowCount - 1), { align: "end" });
    });
  }, [rowCount, virtualizer]);

  return { stickyIndex, stickyPinned, keepFollowingToEnd };
}
