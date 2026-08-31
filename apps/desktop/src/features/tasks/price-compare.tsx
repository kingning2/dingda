/**
 * price_compare 内部节点 → 用户可见思考文案与 content 解析。
 */

import type { ReactNode } from "react";
import type { AgentRunRecord, AgentRunStep } from "@desk/platform/ipc/agent-run";
import { TypewriterText, type AgentThought, type AgentThoughtStatus } from "@desk/ui";

/** 内部节点 ID（seek / 调试），不对用户展示。 */
export const PRICE_COMPARE_NODE_IDS = [
  "web_research",
  "article_analyze",
  "planner",
  "crawl",
  "normalize",
  "match",
  "analyze",
  "keyword_refine",
  "finalize",
] as const;

/** @deprecated 仅保留兼容；UI 请用 thoughtLabelForNode */
export const PRICE_COMPARE_STEP_LABELS: { id: string; label: string }[] = [
  { id: "web_research", label: "网页调研" },
  { id: "article_analyze", label: "文章分析" },
  { id: "planner", label: "规划关键词" },
  { id: "crawl", label: "渠道采集" },
  { id: "normalize", label: "字段归一" },
  { id: "match", label: "同款配对" },
  { id: "analyze", label: "核验分析" },
  { id: "finalize", label: "成文" },
];

const THOUGHT_LABELS: Record<string, string> = {
  web_research: "检索相关资料与行情",
  article_analyze: "阅读材料并提炼要点",
  planner: "规划比对方向与搜索词",
  crawl: "采集各渠道商品",
  keyword_refine: "扩大搜索范围，继续采集",
  analyze: "交叉核验价格与利润",
};

/** 不向用户单独展示的中间节点。 */
const SILENT_NODES = new Set(["normalize", "match", "finalize"]);

const THOUGHT_STATUS: Record<string, AgentThoughtStatus> = {
  pending: "done",
  running: "running",
  done: "done",
  error: "error",
};

export function thoughtLabelForNode(node: string): string {
  if (THOUGHT_LABELS[node]) {
    return THOUGHT_LABELS[node];
  }
  if (node === "normalize" || node === "match") {
    return "整理并比对商品";
  }
  return "处理中";
}

export function mapThoughtStatus(raw: string | undefined): AgentThoughtStatus {
  if (!raw || raw === "pending") {
    return "done";
  }
  return THOUGHT_STATUS[raw] ?? "done";
}

export function kindLabel(kind: string): string {
  if (kind === "price_compare") {
    return "选品比价";
  }
  return kind || "任务";
}

export function stateLabel(state: string): string {
  switch (state) {
    case "running":
      return "运行中";
    case "paused":
      return "已暂停";
    case "waiting_network":
      return "等待网络";
    case "completed":
      return "已完成";
    case "failed":
      return "失败";
    case "cancelled":
      return "已取消";
    case "created":
      return "已创建";
    default:
      return state || "未知";
  }
}

export function formatRunTime(ms: number): string {
  if (!ms) {
    return "—";
  }
  try {
    return new Date(ms).toLocaleString();
  } catch {
    return "—";
  }
}

export function canSeekToNode(run: AgentRunRecord | null, node: string): boolean {
  if (!run) {
    return false;
  }
  if (node === PRICE_COMPARE_NODE_IDS[0]) {
    return true;
  }
  const step = run.steps.find((item) => item.node === node);
  if (!step) {
    return false;
  }
  return step.status === "done" || step.status === "error" || step.status === "running";
}

export function progressLabel(run: AgentRunRecord): string {
  if (run.state === "completed") {
    return "已完成";
  }
  if (run.state === "failed") {
    return "失败";
  }
  if (run.state === "cancelled") {
    return "已取消";
  }
  if (run.state === "paused") {
    return "已暂停";
  }
  if (run.state === "waiting_network") {
    return "等待网络";
  }
  const running = run.steps.find((step) => step.status === "running");
  if (running) {
    return thoughtLabelForNode(running.node);
  }
  return stateLabel(run.state);
}

type SourcePreview = {
  title: string;
  url: string;
  snippet?: string;
};

type ItemPreview = {
  platform?: string;
  title: string;
  url: string;
  price?: string;
  snippet?: string;
};

function tryParseJson(raw: string): unknown {
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    return null;
  }
}

export function parseWebResearchContent(content: string | undefined): {
  text: string;
  sources: SourcePreview[];
} | null {
  if (!content?.trim()) {
    return null;
  }
  const parsed = tryParseJson(content);
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    const obj = parsed as { text?: unknown; sources?: unknown };
    const sources: SourcePreview[] = [];
    if (Array.isArray(obj.sources)) {
      for (const item of obj.sources) {
        if (!item || typeof item !== "object") {
          continue;
        }
        const row = item as Record<string, unknown>;
        sources.push({
          title: String(row.title || row.url || "来源"),
          url: String(row.url || ""),
          snippet: row.snippet != null ? String(row.snippet) : undefined,
        });
      }
    }
    return {
      text: String(obj.text || ""),
      sources,
    };
  }
  return { text: content, sources: [] };
}

export function parseCrawlContent(content: string | undefined): {
  text: string;
  items: ItemPreview[];
} | null {
  if (!content?.trim()) {
    return null;
  }
  const parsed = tryParseJson(content);
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    const obj = parsed as { text?: unknown; items?: unknown };
    const items: ItemPreview[] = [];
    if (Array.isArray(obj.items)) {
      for (const item of obj.items) {
        if (!item || typeof item !== "object") {
          continue;
        }
        const row = item as Record<string, unknown>;
        items.push({
          platform: row.platform != null ? String(row.platform) : undefined,
          title: String(row.title || row.url || "商品"),
          url: String(row.url || ""),
          price: row.price != null ? String(row.price) : undefined,
          snippet: row.snippet != null ? String(row.snippet) : undefined,
        });
      }
    }
    return {
      text: String(obj.text || ""),
      items,
    };
  }
  return { text: content, items: [] };
}

/** 运行日志用：把 step content 收成可读文本（含来源列表）。 */
export function formatStepLogText(node: string, content: string | undefined): string {
  if (!content?.trim()) {
    return "";
  }

  if (node === "web_research") {
    const parsed = parseWebResearchContent(content);
    if (!parsed) {
      return content.slice(0, 2000);
    }
    const sourceLines = parsed.sources.map((item, index) => {
      const note = item.snippet ? ` — ${item.snippet}` : "";
      return `${index + 1}. ${item.title}${item.url ? ` (${item.url})` : ""}${note}`;
    });
    const parts = [
      parsed.text.trim(),
      sourceLines.length > 0 ? `来源（${sourceLines.length}）：\n${sourceLines.join("\n")}` : "",
    ].filter(Boolean);
    return parts.join("\n\n").slice(0, 4000);
  }

  if (node === "crawl") {
    const parsed = parseCrawlContent(content);
    if (!parsed) {
      return content.slice(0, 2000);
    }
    if (parsed.items.length === 0) {
      return parsed.text;
    }
    const itemLines = parsed.items.map((item, index) => {
      const price = item.price ? ` · ${item.price}` : "";
      return `${index + 1}. ${item.platform ? `${item.platform} · ` : ""}${item.title}${price}`;
    });
    return `${parsed.text}\n${itemLines.join("\n")}`.slice(0, 4000);
  }

  return content.slice(0, 4000);
}

/** 把 step content 收成可展开的 React 节点。 */
export function renderStepDetail(
  node: string,
  content: string | undefined,
  streaming = false,
): ReactNode {
  if (!content?.trim()) {
    return undefined;
  }

  if (node === "web_research") {
    const parsed = parseWebResearchContent(content);
    if (!parsed) {
      return undefined;
    }
    return (
      <div className="space-y-2 py-0.5">
        {parsed.text ? (
          <p className="whitespace-pre-wrap text-foreground/80">
            <TypewriterText text={parsed.text} streaming={streaming} />
          </p>
        ) : null}
        {parsed.sources.length > 0 ? (
          <ul className="space-y-1.5">
            {parsed.sources.map((item) => (
              <li
                key={item.url || item.title}
                className="rounded-[var(--radius-md)] bg-background/70 px-2 py-1.5"
              >
                {item.url ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-foreground hover:underline"
                  >
                    {item.title}
                  </a>
                ) : (
                  <span className="font-medium text-foreground">{item.title}</span>
                )}
                {item.snippet ? (
                  <p className="mt-0.5 text-muted-foreground">{item.snippet}</p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  if (node === "crawl") {
    const parsed = parseCrawlContent(content);
    if (!parsed) {
      return undefined;
    }
    return (
      <div className="space-y-2 py-0.5">
        {parsed.text ? <p className="text-foreground/80">{parsed.text}</p> : null}
        {parsed.items.length > 0 ? (
          <ul className="space-y-1.5">
            {parsed.items.map((item) => (
              <li
                key={`${item.platform ?? ""}-${item.url || item.title}`}
                className="rounded-[var(--radius-md)] bg-background/70 px-2 py-1.5"
              >
                <p className="font-medium text-foreground">
                  {item.platform ? `${item.platform} · ` : ""}
                  {item.url ? (
                    <a href={item.url} target="_blank" rel="noreferrer" className="hover:underline">
                      {item.title}
                    </a>
                  ) : (
                    item.title
                  )}
                </p>
                {item.price || item.snippet ? (
                  <p className="mt-0.5 text-muted-foreground">{item.price || item.snippet}</p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  return (
    <p className="whitespace-pre-wrap text-foreground/80">
      <TypewriterText text={content} streaming={streaming} />
    </p>
  );
}

export function buildAgentThoughts(run: AgentRunRecord | null): AgentThought[] {
  const steps = [...(run?.steps ?? [])].sort((a, b) => a.index - b.index);
  const thoughts: AgentThought[] = [];

  for (const step of steps) {
    if (SILENT_NODES.has(step.node)) {
      continue;
    }
    if (step.status === "pending") {
      continue;
    }

    const status = mapThoughtStatus(step.status);
    const plainDetail = formatStepLogText(step.node, step.content ?? step.detail);
    const detail = renderStepDetail(step.node, step.content ?? step.detail, status === "running");
    thoughts.push({
      id: `${step.node}:${step.index}`,
      label: thoughtLabelForNode(step.node),
      status,
      detail: detail ?? undefined,
      detailText: plainDetail || undefined,
      detailStreaming: status === "running",
    });
  }

  return thoughts;
}

export function upsertRunStep(
  run: AgentRunRecord,
  patch: {
    node?: string;
    index?: number;
    status: string;
    detail?: string;
    content?: string;
    message?: string;
    errorKind?: string;
    model?: string;
  },
): AgentRunRecord {
  if (!patch.node && patch.index == null) {
    return {
      ...run,
      state:
        patch.status === "completed" ||
        patch.status === "failed" ||
        patch.status === "cancelled" ||
        patch.status === "paused" ||
        patch.status === "waiting_network"
          ? patch.status
          : run.state,
      reply: patch.status === "completed" ? patch.content ?? patch.detail ?? run.reply : run.reply,
      error: patch.status === "failed" ? patch.message || run.error : run.error,
      updatedAt: Date.now(),
    };
  }

  const steps = [...run.steps];
  const idx =
    patch.index != null
      ? steps.findIndex((step) => step.index === patch.index)
      : steps.findIndex((step) => step.node === patch.node);

  const next: AgentRunStep = {
    id: patch.node ? `${run.id}:${patch.node}` : `step-${patch.index ?? steps.length}`,
    node: patch.node ?? (idx >= 0 ? steps[idx]!.node : "unknown"),
    index: patch.index ?? (idx >= 0 ? steps[idx]!.index : steps.length),
    status: patch.status,
    label: patch.message,
    detail: patch.detail,
    errorKind: patch.errorKind,
    model: patch.model,
    content: patch.content,
  };

  if (idx >= 0) {
    const prev = steps[idx]!;
    steps[idx] = {
      ...prev,
      ...next,
      content: patch.content ?? prev.content,
      detail: patch.detail ?? prev.detail,
      label: patch.message ?? prev.label,
    };
  } else {
    steps.push(next);
    steps.sort((a, b) => a.index - b.index);
  }

  return {
    ...run,
    steps,
    updatedAt: Date.now(),
  };
}
