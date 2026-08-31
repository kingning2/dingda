/**
 * 路由 → 页面元信息（中文标题 / 描述）。
 */

import { listWorkspaceFeatures } from "@feature/workspace-features";

export interface PageMeta {
  title: string;
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
    title: "工作台",
    description: "今天有什么值得卖",
  },
  "/dashboard": {
    title: "工作台",
    description: "今天有什么值得卖",
  },
  "/discovery": {
    title: "选品发现",
    description: "发现值得卖的商品机会",
  },
  "/discovery/high-profit": { title: "高利润机会" },
  "/discovery/hot": { title: "热门机会" },
  "/discovery/blue-ocean": { title: "蓝海机会" },
  "/discovery/new": { title: "新发现" },
  "/discovery/start": { title: "开始选品" },
  "/products": {
    title: "商品库",
    description: "标准商品目录",
  },
  "/profit": { title: "利润分析" },
  "/profit/calculator": { title: "利润计算器" },
  "/profit/templates": { title: "成本模板" },
  "/monitoring": { title: "价格 / 竞品监控" },
  "/monitoring/subscriptions": { title: "监控列表" },
  "/monitoring/alerts": { title: "监控提醒" },
  "/monitoring/rules": { title: "监控规则" },
  "/tasks": { title: "任务中心" },
  "/settings": { title: "设置" },
  "/settings/general": { title: "通用设置" },
  "/settings/accounts": { title: "账号" },
  "/settings/collection": { title: "采集设置" },
  "/settings/profit": { title: "利润默认" },
  "/settings/ai": { title: "AI 模型" },
  "/settings/subscription": { title: "订阅" },
  ...featurePageMeta,
};

export function getPageMeta(pathname: string): PageMeta {
  if (pathname.startsWith("/products/") && pathname !== "/products") {
    return { title: "商品详情", description: "这个商品为什么值得卖" };
  }
  if (pathname.startsWith("/tasks/") && pathname !== "/tasks") {
    return { title: "任务中心" };
  }

  return pageMetaByPath[pathname] ?? { title: "DingDa" };
}
