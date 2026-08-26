/**
 * 路由 → 页面元信息（中文标题 / 描述）。
 *
 * Feature 页优先取自 {@link listWorkspaceFeatures}；渠道管理页走 platform-routes。
 *
 * @author coisini
 * @created 2026-07-20
 */

import { CHANNEL_MANAGE_ROOT } from "@desk/platform/compile";
import { manageTitleFromPath } from "@platform-routes";
import { listWorkspaceFeatures } from "@feature/workspace-features";

/**
 * 页面元信息。
 *
 * @author coisini
 * @created 2026-07-20
 */
export interface PageMeta {
  /** 页面标题。 */
  title: string;
  /** 页面描述。 */
  description?: string;
}

const featurePageMeta: Record<string, PageMeta> = Object.fromEntries(
  listWorkspaceFeatures().map((feature) => [
    feature.path,
    {
      title: feature.navItem.label,
      description: feature.description,
    },
  ]),
);

const pageMetaByPath: Record<string, PageMeta> = {
  "/": {
    title: "首页",
    description: "渠道经营总览与快捷入口",
  },
  [CHANNEL_MANAGE_ROOT]: {
    title: "首页",
    description: "渠道经营总览与快捷入口",
  },
  ...featurePageMeta,
};

/**
 * 按路径取页面元信息。
 *
 * @author coisini
 * @created 2026-07-20
 *
 * @param pathname - 路由路径
 * @returns 元信息；未知路径回退到应用名
 */
export function getPageMeta(pathname: string): PageMeta {
  const manageTitle = manageTitleFromPath(pathname);
  if (manageTitle) {
    return {
      title: manageTitle,
      description: "渠道经营与管理",
    };
  }

  return pageMetaByPath[pathname] ?? { title: "DingDa" };
}
