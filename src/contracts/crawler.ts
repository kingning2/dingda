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

/** 闲鱼商品留言。 */
export interface CrawlProductComment {
  author: string;
  content: string;
  time?: string | null;
  reply?: string | null;
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
  /** 闲鱼「想要」人数（详情接口）。 */
  want_count?: string | null;
  browse_count?: string | null;
  /** 商品正文描述（详情接口）。 */
  desc?: string | null;
  /** 闲鱼留言（详情接口）。 */
  comments?: CrawlProductComment[];
  /** 小红书图片 OCR。 */
  ocr_text?: string | null;
  /** 小红书正文 + OCR 合并文本。 */
  content_text?: string | null;
  /** 小红书笔记类型：normal / video。 */
  note_type?: string | null;
  /** 小红书搜索下发；拉详情必须带回，否则 300031。 */
  xsec_token?: string | null;
  crawled_at: string;
}

export interface CrawlSearchRequest {
  platform: CrawlPlatform;
  query: string;
  limit?: number;
  cookie?: string | null;
}

export interface CrawlProductRequest {
  platform: CrawlPlatform;
  item_id: string;
  cookie?: string | null;
  xsec_token?: string | null;
}

export interface CrawlProductResponse {
  ok: boolean;
  platform: CrawlPlatform | string;
  item?: CrawlProductItem | null;
  error_code?: string | null;
  message?: string | null;
}

export interface CrawlSearchResponse {
  task_id: string;
  status: CrawlTaskStatusView;
  items: CrawlProductItem[];
  total: number;
  /** 对应平台搜索页，供对话内嵌展示。 */
  search_url?: string | null;
  error_code?: string | null;
  message?: string | null;
}

export interface CrawlHistoryItem {
  id: string;
  platform: CrawlPlatform;
  query: string;
  total: number;
  status: CrawlTaskStatusView;
  created_at: string;
}
