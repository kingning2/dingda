/**
 * 自主爬虫契约 — 与 Python crawler API 对齐。
 * 用户手动输入关键词发起爬取，不由 AI Agent 主导。
 */

export type CrawlPlatform = "xianyu" | "ali1688" | "xiaohongshu";

/** 爬取任务状态（由服务端返回）。 */
export interface CrawlTaskStatusView {
  state: string;
  label: string;
  hint?: string | null;
  badge_class: string;
}

/** 单条爬取结果。 */
export interface CrawlProductItem {
  id: string;
  title: string;
  price: string;
  platform: CrawlPlatform;
  seller?: string;
  location?: string;
  image_url?: string;
  product_url?: string;
  crawled_at: string;
}

export interface CrawlSearchRequest {
  platform: CrawlPlatform;
  query: string;
}

export interface CrawlSearchResponse {
  task_id: string;
  status: CrawlTaskStatusView;
  items: CrawlProductItem[];
  total: number;
}

export interface CrawlHistoryItem {
  id: string;
  platform: CrawlPlatform;
  query: string;
  total: number;
  status: CrawlTaskStatusView;
  created_at: string;
}
