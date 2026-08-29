import type { Metadata } from "next";
import { createPageMetadata, SEO } from "@/lib/seo";

type DemoMeta = { title: string; description: string };

/** 对齐 SpyX `demoMetaInfo.js`：控制台演示页独立 title / description，默认 noindex。 */
export const CONSOLE_DEMO_META: Record<string, DemoMeta> = {
  "/console": {
    title: "工作台演示 — Agent 选品总览",
    description:
      "叮答工作台演示：今日商品机会、高利润摘要、Agent 比价探索任务。对齐桌面端 dashboard。",
  },
  "/console/discovery/high-profit": {
    title: "高利润机会 — 选品发现演示",
    description: "查看 Agent + 爬虫筛出的高利润选品机会列表示例，含利润率、竞争度与机会评分。",
  },
  "/console/discovery/hot": {
    title: "热门机会 — 选品发现演示",
    description: "浏览近期闲鱼与 1688 热门商品机会，了解叮答如何捕捉爆款趋势。",
  },
  "/console/discovery/blue-ocean": {
    title: "蓝海机会 — 选品发现演示",
    description: "低竞争、有利润空间的蓝海品类机会列表示例，适合扩品类与新手入门。",
  },
  "/console/discovery/new": {
    title: "新发现 — 选品发现演示",
    description: "Agent 最新探索到的选品机会预览，展示自动发现与比价分析结果。",
  },
  "/console/discovery/start": {
    title: "开始选品 — 三种场景演示",
    description: "知道商品、知道品类、完全不知道卖什么——三种选品入口与 Agent 探索流程演示。",
  },
  "/console/products": {
    title: "商品库演示",
    description: "标准商品目录与指标沉淀示例，对齐桌面端商品库模块。",
  },
  "/console/profit/calculator": {
    title: "利润计算器演示",
    description: "采购价、售价与成本项利润测算界面演示，帮助判断有没有利润空间。",
  },
  "/console/profit/templates": {
    title: "成本模板演示",
    description: "常用成本项模板与利润默认参数配置界面演示。",
  },
  "/console/monitoring/subscriptions": {
    title: "监控订阅演示",
    description: "价格与竞品监控订阅列表示例，展示持续跟踪选品机会的能力。",
  },
  "/console/monitoring/alerts": {
    title: "告警记录演示",
    description: "价格、利润与竞品变动告警历史示例。",
  },
  "/console/monitoring/rules": {
    title: "监控规则配置演示",
    description: "自定义监控阈值与通知规则的配置界面示例。",
  },
  "/console/tasks": {
    title: "任务中心演示",
    description: "AgentRun 任务列表示例，含 price_compare 比价探索任务状态与进度。",
  },
  "/console/settings/general": {
    title: "通用设置演示",
    description: "叮答桌面端通用偏好设置界面骨架演示。",
  },
  "/console/settings/accounts": {
    title: "账号设置演示",
    description: "闲鱼与 1688 账号绑定与管理界面演示。",
  },
  "/console/settings/collection": {
    title: "采集设置演示",
    description: "爬虫采集频率、范围与渠道参数配置界面演示。",
  },
  "/console/settings/profit": {
    title: "利润默认设置演示",
    description: "默认成本项、运费与利润率假设配置界面演示。",
  },
  "/console/settings/ai": {
    title: "AI 模型设置演示",
    description: "Agent 所用大模型与推理参数配置界面演示。",
  },
};

function normalizePath(path: string) {
  if (path === "/") return path;
  return path.replace(/\/+$/, "") || "/";
}

export function demoPageMetadata(path: string, options?: { noIndex?: boolean }): Metadata {
  const key = normalizePath(path);
  const entry = CONSOLE_DEMO_META[key];
  const noIndex = options?.noIndex ?? key !== "/console";

  return createPageMetadata({
    title: entry?.title ?? `控制台演示 | ${SEO.siteNameShort}`,
    description: entry?.description ?? SEO.defaultDescription,
    path: key === "/" ? "/" : `${key}/`,
    noIndex,
  });
}
