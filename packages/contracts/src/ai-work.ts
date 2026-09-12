/**
 * AI 工作详情契约 — 与 Python agent API 对齐。
 * 页面只消费后端返回的完整快照，不在前端定义状态枚举。
 */

import type { CrawlProductItem } from "./crawler";
import type { ComposerAgentOption, ComposerAttachmentView } from "./composer";

export interface AgentWorkStatusView {
  state: string;
  label: string;
  hint?: string | null;
  badge_class: string;
}

/** 对话内嵌的「页面」快照（浏览器框 + 可选截图）。 */
export interface AgentWorkStepPageView {
  url: string;
  title: string;
  focus_label?: string | null;
  /** true 时显示加载态。 */
  loading?: boolean;
  screenshot_url?: string | null;
}

/**
 * 步骤类型：后端驱动前端挂哪些块。
 * - tool：普通工具
 * - browser_crawl：页面爬取（可挂 PageCard）
 * - product_sample：抽样详情（可挂商品条）
 * - thinking：思考（一般走 message.thinking，少用 step）
 */
export type AgentWorkStepKind = "tool" | "browser_crawl" | "product_sample" | "thinking";

/** 单条执行步骤（工具调用 / 子任务）。 */
export interface AgentWorkStepView {
  id: string;
  label: string;
  hint?: string | null;
  /**
   * 步骤类型。缺省按 tool。
   * status.state 约定：pending 等待 / running 执行中 / ready 已完成 / error 失败
   */
  kind?: AgentWorkStepKind | null;
  status: AgentWorkStatusView;
  /** 关联的浏览帧，便于从步骤跳转到对应页面截图。 */
  browser_frame_id?: string | null;
  /** 页面爬取步骤携带的直播/结果页快照。 */
  page?: AgentWorkStepPageView | null;
}

export interface AgentWorkMessageView {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  /** 模型推理过程，由服务端流式增量推送。 */
  thinking?: string | null;
  /** 开始思考/执行的时间（ISO），用于界面计时。 */
  thinking_started_at?: string | null;
  /** 思考/执行总秒数（完成后落库，刷新可回看）。 */
  thinking_duration_sec?: number | null;
  steps?: AgentWorkStepView[];
  /**
   * 按事件到达顺序交错的时间线（思考 / 工具 / 正文）。
   * 有值时 UI 按此顺序渲染，避免工具全堆在底部。
   */
  timeline?: AgentWorkTimelineEntry[];
  attachments?: ComposerAttachmentView[];
}

/** 助手消息时间线条目。 */
export type AgentWorkTimelineEntry =
  | { kind: "thinking"; id: string; text: string }
  | { kind: "step"; id: string }
  | { kind: "text"; id: string; text: string };

/**
 * 已离开页面的最后一帧截图（历史归档）。
 * 后端在页面切换前抓取最后一帧并追加到 history。
 */
export interface AgentBrowserFrameView {
  id: string;
  url: string;
  title: string;
  focus_label?: string | null;
  screenshot_url: string;
  captured_at: string;
  label?: string | null;
}

/**
 * 当前正在浏览的页面快照。
 * 进行中可能尚无 screenshot_url；离开后会归档到 browser_history。
 */
export interface AgentBrowserLiveView {
  frame_id?: string | null;
  url: string;
  title: string;
  status: AgentWorkStatusView;
  progress_hint?: string | null;
  screenshot_url?: string | null;
  focus_label?: string | null;
}

/** 本任务抓取到的单条商品，关联到产生它的执行步骤（对话内小卡片展示）。 */
export interface AgentWorkProductItem extends CrawlProductItem {
  step_id: string;
  step_label?: string | null;
}

/** 本任务已抓取商品汇总（由服务端增量推送）。 */
export interface AgentWorkProductsView {
  items: AgentWorkProductItem[];
  total: number;
  status: AgentWorkStatusView;
}

/** 最终推荐商品，含推荐理由与依据（结果 Tab 展示）。 */
export interface AgentWorkRecommendationItem extends AgentWorkProductItem {
  recommendation_reason: string;
  recommendation_basis: string;
}

export interface AgentWorkRecommendationsView {
  items: AgentWorkRecommendationItem[];
  total: number;
  status: AgentWorkStatusView;
  /** 整体推荐说明，由服务端生成。 */
  summary?: string | null;
}

/** 比价来源商品（通常是闲鱼/小红书/淘宝商品）。 */
export interface AgentWorkComparisonSourceView {
  item_id: string;
  title: string;
  platform: string;
  url: string;
  image_url: string;
  price?: string | null;
  seller?: string | null;
}

/** 1688 比价候选。 */
export interface AgentWorkComparisonItemView {
  id: string;
  title: string;
  price: string;
  platform: "ali1688";
  seller?: string | null;
  image_url?: string | null;
  product_url?: string | null;
  compare_label?: string | null;
  compare_reasons: string[];
  compare_score?: number | null;
  similarity_score?: number | null;
  merchant_rating?: number | null;
  repurchase_rate?: number | null;
  sold_count?: number | null;
  yx_index?: number | null;
  stock_amount?: number | null;
  quantity_begin?: number | null;
  unit?: string | null;
  round?: number | null;
  search_query?: string | null;
  search_mode?: string | null;
}

/** 一次 1688 同款比价快照。 */
export interface AgentWorkComparisonView {
  kind: "price_compare";
  platform: string;
  source: AgentWorkComparisonSourceView;
  items: AgentWorkComparisonItemView[];
  total_candidates: number;
  rounds: number;
  /** 每次 compare Tool 实际执行的检索策略 / 查询。 */
  queries: string[];
  status: AgentWorkStatusView;
}

export interface AgentWorkDetailView {
  work_id: string;
  title: string;
  status: AgentWorkStatusView;
  messages: AgentWorkMessageView[];
  products: AgentWorkProductsView;
  recommendations: AgentWorkRecommendationsView;
  /** 最近一次 compare Tool 的货源对比；旧快照可缺省。 */
  comparison?: AgentWorkComparisonView | null;
  browser_live: AgentBrowserLiveView;
  /** 按时间顺序排列的已归档页面（每页仅保留最后一帧截图）。 */
  browser_history: AgentBrowserFrameView[];
  composer_placeholder?: string | null;
  can_send: boolean;
  /** 当前任务绑定的执行 Agent（由 daemon 返回）。 */
  composer_agent_id?: string | null;
  composer_model_id?: string | null;
  /** 本机已接入、可切换的 Agent 列表。 */
  composer_agents: ComposerAgentOption[];
  /**
   * 外部 CLI 续聊 session / thread id。
   * 与 cli_session_runtime_id 成对；换 Agent 时清空。
   */
  cli_session_id?: string | null;
  /** 产生 cli_session_id 的 runtime id（如 opencode / codex）。 */
  cli_session_runtime_id?: string | null;
}

export interface AgentWorkSendRequest {
  work_id: string;
  message: string;
  agent_id?: string | null;
  model_id?: string | null;
  attachments?: ComposerAttachmentView[];
}
