/**
 * 爬虫支持的平台标签常量。
 */

import type { CrawlPlatform } from "@v2/contracts/crawler";

/** 爬虫搜索页的平台标签列表。 */
export const CRAWL_PLATFORM_TABS: Array<{ id: CrawlPlatform; label: string }> = [
  { id: "xianyu", label: "闲鱼" },
  { id: "ali1688", label: "1688" },
  { id: "xiaohongshu", label: "小红书" },
];
