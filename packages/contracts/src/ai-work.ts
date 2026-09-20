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

/**
 * 最近工作列表项（首页 / 全部项目）。
 *
 * 之所以放在 contracts 而不是 ui-agent：这是 `/v1/agent/works` 的线协议 DTO，
 * 且被跨域共享的 UI 状态（@v2/app-state）与首页域（@v2/ui-home）消费。
 * 留在 ui-agent 会让状态包反向依赖业务包，形成环。
 */
export interface AgentWorkSummary {
  work_id: string;
  title: string;
  updated_at: number;
  status_label?: string | null;
  status_state?: string | null;
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
 * - browser_crawl：页面爬取（可挂 PageCard / 直播页卡）
 * - login：扫码登录（挂独立扫码块，不用直播页卡样式）
 */
export type AgentWorkStepKind =
  | "tool"
  | "browser_crawl"
  | "login";

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
  /**
   * 原始命令行（仅命令执行类步骤）。不参与 label / hint 推导 ——
   * 那是给用户看的，这里只落进「查看原始调用」折叠区供排查。
   */
  command?: string | null;
  /** 该步的完整原始输出，不截断；同样只进折叠区。 */
  output?: string | null;
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
  /** 父会话派出的子会话（worker），按时间顺序；子块自己的步骤不再混进 steps。 */
  children?: AgentWorkChildView[];
  attachments?: ComposerAttachmentView[];
}

/** 助手消息时间线条目。 */
export type AgentWorkTimelineEntry =
  | { kind: "thinking"; id: string; text: string }
  | { kind: "step"; id: string }
  | { kind: "text"; id: string; text: string }
  | { kind: "child"; id: string };

/**
 * 派出的子会话（worker）子块。
 *
 * 由父 SSE 以 ``childEvent`` 中继折叠而来：子会话状态、步骤与正文都在这里，
 * 不摊进父消息的 steps —— 否则父子步骤会混成一条时间线。
 */
export interface AgentWorkChildView {
  /** 子 run_id，也是 childEvent 的归并键。 */
  run_id: string;
  role: string;
  /** 子块标题（缺省由 role 推导）。 */
  label?: string | null;
  /** 子会话当前 phase 原文（pending / running / needs_repair / completed / failed / cancelled）。 */
  phase: string;
  status: AgentWorkStatusView;
  /** 子会话当前动作文案。 */
  step?: string | null;
  steps: AgentWorkStepView[];
  timeline: AgentWorkTimelineEntry[];
  /** 子会话累计正文。 */
  content: string;
  /** 子会话累计思考。 */
  thinking: string;
  /** 子会话终局摘要，由服务端在收尾时写入。 */
  summary?: string | null;
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

/** 一个候选品类的选品打分结果。 */
export interface AgentWorkSelectionItemView {
  /** 稳定键：platform + keyword。 */
  id: string;
  keyword: string;
  platform: string;
  /** 0~100 综合分；一个维度都没量到时是 null（不是 0）。 */
  score: number | null;
  /** 证据覆盖率：量到的维度权重 / 全部权重。覆盖率低的分不该和高覆盖率平起平坐。 */
  evidence_coverage: number | null;
  sample_size: number;
  detail_size: number;
  distinct_sellers: number;
  price_p25: number | null;
  price_median: number | null;
  price_p75: number | null;
  demand_total: number | null;
  sold_count: number;
  on_sale_count: number;
  /** 量到售出状态的条数；售出比例的分母是它，不是 sample_size。 */
  state_known: number;
  /** 货源可得性。本轮恒为 unverified —— 1688 额度失效，没查过货源。 */
  availability: string;
  evidence_status: string;
  /** 人类可读的算分依据。 */
  reasons: string[];
  /** 缺证据的维度，逐条写明缺什么 —— 也就是「没量到」的部分。 */
  evidence_gaps: string[];
  dimensions: Record<string, number>;
}

/** 一次选品快照。 */
export interface AgentWorkSelectionView {
  kind: "product_selection";
  /** 这一批覆盖的平台。**分数只在同一平台内可比**，跨平台行不能直接比大小。 */
  platforms: string[];
  items: AgentWorkSelectionItemView[];
  /** 没取到样本的候选：只列出来，不参与排名。 */
  excluded: AgentWorkSelectionExcludedView[];
  /** 预算用完 / 被取消，结果不完整。 */
  partial: boolean;
  reason?: string | null;
  status: AgentWorkStatusView;
}

/** 没取到样本、因此不参与排名的候选。 */
export interface AgentWorkSelectionExcludedView {
  keyword: string;
  platform: string;
  error_code: string;
}

/**
 * 鉴定同款表的一行。**本商品自己也是其中一行**（`is_target` 为真）。
 *
 * 这么排是为了直接回答转卖决策的第二半 —— 「还有没有更便宜的同类」。
 */
export interface AgentWorkAppraisalItemView {
  /** 稳定键：item_id。 */
  id: string;
  title: string;
  price: string;
  platform: string;
  url: string;
  seller?: string | null;
  image_url?: string | null;
  want_count?: string | null;
  browse_count?: string | null;
  sold_state?: string | null;
  /** 本商品自己那一行。正文里报的价格必须对得上它。 */
  is_target: boolean;
  /** 相对本商品价高/低多少（%，正 = 比本商品贵）；本商品自己是 0。 */
  price_delta_pct?: number | null;
}

/** 一次单品鉴定快照：一个具体商品与它的一批同款摆在一起下的判词。 */
export interface AgentWorkAppraisalView {
  kind: "product_appraisal";
  /** 同款是拿什么词搜出来的 —— 价差对不上时，这是追查的起点。 */
  query: string;
  /** 0~100 综合分；判不了时是 null（不是 0）。 */
  score: number | null;
  /** 四态：worth / caution / skip / insufficient。别自己改口径。 */
  verdict: string;
  verdict_label: string;
  verdict_reason: string;
  evidence_coverage: number | null;
  dimensions: Record<string, number>;
  reasons: string[];
  /** 没量到的维度，逐条写明缺什么 —— 汇报时要如实说「这项没量到」。 */
  evidence_gaps: string[];
  /** 鉴定的主语；拉不到详情时为 null，此时下面是空的。 */
  target: AgentWorkAppraisalItemView | null;
  /** 按价格升序的同款表（含本商品自己那一行）。 */
  comparables: AgentWorkAppraisalItemView[];
  /** 本商品价与同款中位价的相对差；没量到同款价格时为 null。 */
  spread: number | null;
  price_p25: number | null;
  price_median: number | null;
  price_p75: number | null;
  sample_size: number;
  /** 预算用完 / 被取消，结果不完整。 */
  partial: boolean;
  /** 失败时的说明（`target` 为 null 时用）。 */
  message?: string | null;
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
  /**
   * 最近一次选品 Tool 的候选排名；旧快照可缺省。
   *
   * 只保留最近一次、不与上一轮合并：候选分是**平台内归一**出来的，两轮的分不同尺，
   * 叠在一起会让人以为是同一把尺量出来的。
   */
  selection?: AgentWorkSelectionView | null;
  /**
   * 最近一次鉴定 Tool 的判词与同款表；旧快照可缺省。
   *
   * 同为只保留最近一次、不与上一轮合并：换一批同款就是换了参照系，两轮的价差不同尺。
   */
  appraisal?: AgentWorkAppraisalView | null;
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
