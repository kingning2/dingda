/**
 * robots.txt 规则构建 — GEO 文章核心：每个 AI 爬虫独立块 + 显式 Allow。
 */
import { AI_PLATFORMS, GEO_FILES } from "@/lib/seo/ai-crawlers";
import { asset, basePath } from "@/lib/site";

function scoped(path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return basePath ? `${basePath}${normalized}` : normalized;
}

/** 希望被 AI / 搜索收录的公开页面 */
export const INDEXABLE_PATHS = [
  scoped("/"),
  scoped("/faq/"),
  scoped("/console/"),
] as const;

/** GEO 机器可读摘要（AI 爬虫应能直接抓取） */
export const GEO_ASSET_PATHS = [
  asset(GEO_FILES.llms),
  asset(GEO_FILES.aiGeo),
  asset(GEO_FILES.doubaoGeo),
] as const;

/** 演示子页：仅对通用爬虫限制收录，不影响 AI 专用 Allow 块 */
export const DEMO_DISALLOW_PATHS = [
  scoped("/console/discovery/"),
  scoped("/console/settings/"),
  scoped("/console/monitoring/"),
  scoped("/console/profit/"),
  scoped("/console/products/"),
  scoped("/console/tasks/"),
] as const;

/** AI 爬虫完整 Allow 列表：全站 + 关键页 + GEO 文件（文章建议显式写出） */
export function aiCrawlerAllowList(): string[] {
  return ["/", ...INDEXABLE_PATHS, ...GEO_ASSET_PATHS];
}

type RobotsRule = {
  userAgent: string | string[];
  allow?: string | string[];
  disallow?: string | string[];
  crawlDelay?: number;
};

/** 按平台生成 AI 爬虫规则（每平台独立 User-Agent 块） */
export function buildAiCrawlerRules(): RobotsRule[] {
  const allow = aiCrawlerAllowList();

  return AI_PLATFORMS.flatMap((platform) =>
    platform.userAgents.map((userAgent) => ({
      userAgent,
      allow,
      disallow: [] as string[],
    })),
  );
}

/** 通用爬虫规则：允许公开页，演示子路径不收录 */
export function buildDefaultCrawlerRule(): RobotsRule {
  return {
    userAgent: "*",
    allow: ["/", ...INDEXABLE_PATHS, ...GEO_ASSET_PATHS],
    disallow: [...DEMO_DISALLOW_PATHS],
  };
}

/** 传统搜索引擎（与 AI 同样显式允许 GEO 文件） */
export const SEARCH_ENGINE_AGENTS = [
  "Googlebot",
  "Googlebot-Image",
  "Bingbot",
  "Slurp",
  "DuckDuckBot",
  "Applebot",
] as const;

export function buildSearchEngineRules(): RobotsRule[] {
  const allow = aiCrawlerAllowList();

  return SEARCH_ENGINE_AGENTS.map((userAgent) => ({
    userAgent,
    allow,
    disallow: [...DEMO_DISALLOW_PATHS],
  }));
}

export function buildAllRobotsRules(): RobotsRule[] {
  return [...buildAiCrawlerRules(), ...buildSearchEngineRules(), buildDefaultCrawlerRule()];
}
