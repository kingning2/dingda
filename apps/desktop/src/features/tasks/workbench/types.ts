/** 商品比价 Agent 工作台 — 前端契约（与后端无关）。 */

export type ConversationStatus = "idle" | "running" | "completed" | "error";

export interface Conversation {
  id: string;
  title: string;
  updatedAt: number;
  status: ConversationStatus;
  progress: number;
  unread: boolean;
}

export type AgentStepStatus = "pending" | "running" | "success" | "error";

export type AgentStepType = "search" | "tool" | "process" | "analysis" | "report";

export interface AgentStep {
  id: string;
  type: AgentStepType;
  title: string;
  description?: string;
  status: AgentStepStatus;
  startedAt?: number;
  finishedAt?: number;
  duration?: number;
  result?: unknown;
  metadata?: Record<string, unknown>;
}

export interface AgentToolCall {
  id: string;
  runId: string;
  tool: string;
  args: Record<string, unknown>;
  result?: unknown;
  status: "running" | "success" | "error";
  startedAt: number;
  finishedAt?: number;
  duration?: number;
  error?: string;
}

export interface Product {
  id: string;
  title: string;
  image?: string;
  price: number;
  condition?: string;
  platform: string;
  location?: string;
  publishedAt?: string;
  favorites?: number;
  views?: number;
  url?: string;
  aiScore?: number;
  riskScore?: number;
}

export interface PriceBucket {
  label: string;
  min: number;
  max: number;
  average: number;
  count: number;
}

export interface PriceDistributionBin {
  range: string;
  count: number;
}

export interface AnalysisData {
  summary: string[];
  recommendedRange?: { min: number; max: number };
  priceBuckets: PriceBucket[];
  distribution: PriceDistributionBin[];
  recommendation?: {
    productId: string;
    reasons: string[];
    priceAdvantage?: string;
    condition?: string;
    sellerTrust?: string;
    risk?: string;
  };
}

export interface AgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
}

export interface AgentRunState {
  id: string;
  conversationId: string;
  status: ConversationStatus;
  progress: number;
  progressMessage?: string;
  messages: AgentMessage[];
  steps: AgentStep[];
  toolCalls: AgentToolCall[];
  products: Product[];
  analysis: AnalysisData | null;
  error?: string;
}

export type AgentEvent =
  | { type: "run.started"; runId: string }
  | { type: "message.delta"; runId: string; content: string }
  | { type: "step.started"; step: AgentStep }
  | { type: "step.updated"; stepId: string; data: Partial<AgentStep> }
  | { type: "tool.started"; runId: string; tool: AgentToolCall }
  | { type: "tool.finished"; runId: string; toolId: string; result?: unknown; error?: string }
  | { type: "product.found"; product: Product }
  | { type: "progress.updated"; progress: number; message?: string }
  | { type: "analysis.updated"; data: Partial<AnalysisData> }
  | { type: "run.finished"; runId: string }
  | { type: "run.error"; runId: string; error: string };
