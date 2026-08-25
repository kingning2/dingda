/**
 * 路由 → 页面元信息（中文标题 / 描述）。
 *
 * @author coisini
 * @created 2026-07-20
 */

import {
  CHANNEL_MANAGE_ROOT,
} from "@desk/platform/compile";
import { manageTitleFromPath } from "@platform-routes";

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

const pageMetaByPath: Record<string, PageMeta> = {
  "/": {
    title: "首页",
    description: "渠道经营总览与快捷入口",
  },
  "/features/ai": {
    title: "AI 配置",
    description: "管理智能回复与监控任务使用的 AI 账号",
  },
  "/features/chat": {
    title: "客户会话",
    description: "查看买家消息并人工回复",
  },
  [CHANNEL_MANAGE_ROOT]: {
    title: "首页",
    description: "渠道经营总览与快捷入口",
  },
  "/features/knowledge": {
    title: "知识库",
    description: "沉淀商品话术与常见问题，供客服快速检索",
  },
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
