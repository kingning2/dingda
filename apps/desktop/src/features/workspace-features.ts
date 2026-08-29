/**
 * 工作区 Feature 注册表 — 侧栏 / 路由 / 页面元信息的唯一清单。
 *
 * 选品产品：仅注册业务 L1；设置走独立底栏入口；客服/AI 不注册。
 */

import type { ComponentType, SVGProps } from "react";
import { dashboardFeature } from "@feature/dashboard";
import { discoveryFeature, DISCOVERY_AVAILABLE } from "@feature/discovery";
import { productsFeature } from "@feature/products";
import { profitFeature } from "@feature/profit";
import { monitoringFeature } from "@feature/monitoring";
import { tasksFeature } from "@feature/tasks";

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
 */
export const WORKSPACE_FEATURES: WorkspaceFeature[] = [
  {
    ...dashboardFeature,
    navSlot: "header",
    order: 10,
    description: "今天有什么值得卖",
  },
  {
    ...discoveryFeature,
    available: DISCOVERY_AVAILABLE,
    navSlot: "header",
    order: 20,
    description: "发现高利润 / 热门 / 蓝海 / 新商品机会",
  },
  {
    ...productsFeature,
    navSlot: "header",
    order: 30,
    description: "标准商品目录与指标",
  },
  {
    ...profitFeature,
    navSlot: "header",
    order: 40,
    description: "成本模型与利润测算",
  },
  {
    ...monitoringFeature,
    navSlot: "header",
    order: 50,
    description: "价格与竞品监控提醒",
  },
  {
    ...tasksFeature,
    navSlot: "header",
    order: 60,
    description: "选品与采集等业务任务",
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
