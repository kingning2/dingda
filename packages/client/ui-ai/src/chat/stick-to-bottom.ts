/**
 * 贴底跟随意图（对齐 OpenDesign stick-to-bottom）。
 * 仅当「位置上移且几何未变」才算用户逃逸；内容长高不算。
 */

/** 跟随意图：是否在贴底、是否已逃逸。 */
export type FollowIntent = { following: boolean; escaped: boolean };

/** 滚动采样：scrollTop / scrollHeight / clientHeight。 */
export type ScrollSample = {
  scrollTop: number;
  scrollHeight: number;
  clientHeight: number;
};

const BOTTOM_EPS = 8;

/** 判断是否接近底部（误差 8px）。 */
export function nearBottom(sample: ScrollSample): boolean {
  return sample.scrollHeight - sample.clientHeight - sample.scrollTop <= BOTTOM_EPS;
}

/** 根据两次采样推导下一跟随意图。 */
export function nextFollowIntent(
  intent: FollowIntent,
  last: ScrollSample,
  next: ScrollSample,
): FollowIntent {
  const layoutStable =
    last.scrollHeight === next.scrollHeight && last.clientHeight === next.clientHeight;
  const scrolledUp = next.scrollTop + BOTTOM_EPS < last.scrollTop;

  if (layoutStable && scrolledUp) {
    return { following: false, escaped: true };
  }
  if (intent.escaped && nearBottom(next) && next.scrollTop > last.scrollTop) {
    return { following: true, escaped: false };
  }
  return intent;
}
