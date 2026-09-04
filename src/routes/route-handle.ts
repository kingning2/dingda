import type { UIMatch } from "react-router-dom";

export type EntryRouteHandle = {
  /** 页面主标题，由 EntryLayout 统一渲染。 */
  title?: string;
  /** 全宽铺满主区域（AI 工作详情等分栏页）。 */
  fullBleed?: boolean;
};

export function resolveRouteTitle(matches: UIMatch[]): string | undefined {
  for (let index = matches.length - 1; index >= 0; index -= 1) {
    const title = (matches[index].handle as EntryRouteHandle | undefined)?.title;
    if (title) return title;
  }
  return undefined;
}
