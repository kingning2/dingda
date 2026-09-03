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

/** 单条执行步骤（工具调用 / 子任务）。 */
export interface AgentWorkStepView {
  id: string;
  label: string;
  hint?: string | null;
  status: AgentWorkStatusView;
  /** 关联的浏览帧，便于从步骤跳转到对应页面截图。 */
  browser_frame_id?: string | null;
}

export interface AgentWorkMessageView {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  /** 模型推理过程，由服务端流式增量推送。 */
  thinking?: string | null;
  steps?: AgentWorkStepView[];
  attachments?: ComposerAttachmentView[];
}

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

export interface AgentWorkDetailView {
  work_id: string;
  title: string;
  status: AgentWorkStatusView;
  messages: AgentWorkMessageView[];
  products: AgentWorkProductsView;
  recommendations: AgentWorkRecommendationsView;
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
}

export interface AgentWorkSendRequest {
  work_id: string;
  message: string;
  agent_id?: string | null;
  model_id?: string | null;
  attachments?: ComposerAttachmentView[];
}
