/**
 * 工作区 Feature 注册表 — 侧栏 / 路由 / 页面元信息的唯一清单。
 *
 * 各 Feature 在自身 `index.ts` 声明 `navItem` 与可选门控，
 * 本文件汇总后供 Sidebar、Router、page-meta 消费。
 */

import type { ComponentType, SVGProps } from "react";
import { aiFeature } from "@feature/agent";
import { chatFeature } from "@feature/chat";
import { discoveryFeature, DISCOVERY_AVAILABLE } from "@feature/discovery";
import { knowledgeFeature } from "@feature/knowledge";

/** 侧栏图标组件。 */
export type FeatureNavIcon = ComponentType<SVGProps<SVGSVGElement> & { className?: string }>;

/** 侧栏放置区。 */
export type FeatureNavSlot = "header" | "footer";

/** Feature 侧栏条目。 */
export interface FeatureNavItem {
  id: string;
  path: string;
  label: string;
  icon: FeatureNavIcon;
}

/** 可注册的工作区 Feature。 */
export interface WorkspaceFeature {
  id: string;
  path: string;
  navItem: FeatureNavItem;
  /** 侧栏位置；默认 header。 */
  navSlot?: FeatureNavSlot;
  /** 同槽内排序，越小越靠前。 */
  order?: number;
  /** 编译期 / 运行期门控；false 时不进菜单与路由。 */
  available?: boolean;
  /** 页面描述（title-bar / 文档）。 */
  description?: string;
}

/**
 * 全部工作区 Feature（含可能未启用的）。
 * 新增 Feature：在对应 `index.ts` 导出元信息后加入本数组即可。
 */
export const WORKSPACE_FEATURES: WorkspaceFeature[] = [
  {
    ...chatFeature,
    navSlot: "header",
    order: 10,
    description: "查看买家消息并人工回复",
  },
  {
    ...discoveryFeature,
    available: DISCOVERY_AVAILABLE,
    navSlot: "header",
    order: 20,
    description: "闲鱼强需求 × 1688 货源，Agent 比价选品",
  },
  {
    ...knowledgeFeature,
    navSlot: "header",
    order: 30,
    description: "沉淀商品话术与常见问题，供客服快速检索",
  },
  {
    ...aiFeature,
    navSlot: "footer",
    order: 10,
    description: "管理智能回复与双方比价使用的 AI 账号",
  },
];

/** 当前构建下可用的 Feature（已按 order 排序）。 */
export function listWorkspaceFeatures(slot?: FeatureNavSlot): WorkspaceFeature[] {
  return WORKSPACE_FEATURES.filter((feature) => feature.available !== false)
    .filter((feature) => (slot ? (feature.navSlot ?? "header") === slot : true))
    .slice()
    .sort((a, b) => (a.order ?? 100) - (b.order ?? 100));
}

/** 去掉前导 `/`，供 React Router 子路由 path 使用。 */
export function featureRoutePath(feature: WorkspaceFeature): string {
  return feature.path.replace(/^\//, "");
}
