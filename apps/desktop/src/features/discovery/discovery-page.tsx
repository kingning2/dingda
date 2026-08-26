/**
 * 比价选品页 — Agent 对话式执行（对齐 DeepSeek Harness：composer → 步骤 → 最终回复）。
 * 布局无卡片外壳；右侧欠费换模面板可收起。
 */

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import {
  AsyncButton,
  Button,
  IconButton,
  PageScaffold,
  ScrollArea,
  Textarea,
} from "@desk/ui";
import {
  Bot,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  CirclePause,
  Loader2,
  PanelRightClose,
  PanelRightOpen,
  Play,
  Send,
  Square,
  TrendingUp,
  XCircle,
} from "@desk/ui/icons";
import type { AgentRunStep } from "@desk/platform/ipc/agent-run";
import { FailoverPanel } from "./failover-panel";
import { usePriceCompareRun } from "./use-price-compare-run";

const NODE_LABELS: Record<string, string> = {
  web_research: "网页调研",
  article_analyze: "文章分析",
  planner: "规划关键词",
  crawl: "爬虫核验",
  normalize: "字段归一",
  match: "同款配对",
  analyze: "核验分析",
  finalize: "汇总成文",
  price_compare: "比价任务",
};

const PROMPT_SUGGESTIONS = [
  "帮我找闲鱼上高需求、1688 进货差价大的数码配件选品",
  "分析近期适合二手转卖的母婴用品套利机会",
  "找利润空间大的家居收纳类商品，并给出关键词与进货建议",
];

function nodeLabel(node: string): string {
  return NODE_LABELS[node] ?? node;
}

function statusTone(status: string): string {
  switch (status) {
    case "done":
    case "completed":
      return "text-emerald-600 dark:text-emerald-400";
    case "error":
    case "failed":
      return "text-destructive";
    case "running":
      return "text-primary";
    case "paused":
    case "waiting_network":
      return "text-amber-600 dark:text-amber-400";
    default:
      return "text-muted-foreground";
  }
}

function StatusIcon({ status }: { status: string }) {
  const className = `size-3.5 shrink-0 ${statusTone(status)}`;
  if (status === "running") {
    return <Loader2 className={`${className} animate-spin`} aria-hidden />;
  }
  if (status === "done" || status === "completed") {
    return <CheckCircle className={className} aria-hidden />;
  }
  if (status === "error" || status === "failed") {
    return <XCircle className={className} aria-hidden />;
  }
  if (status === "paused" || status === "waiting_network") {
    return <CirclePause className={className} aria-hidden />;
  }
  return <Loader2 className={`${className} opacity-40`} aria-hidden />;
}

interface StepMediaItem {
  title: string;
  url?: string;
  snippet?: string;
  image?: string;
  platform?: string;
  price?: string;
  query?: string;
}

interface StepPayload {
  text: string;
  sources: StepMediaItem[];
  items: StepMediaItem[];
}

function parseStepPayload(content?: string): StepPayload {
  if (!content) {
    return { text: "", sources: [], items: [] };
  }
  const trimmed = content.trim();
  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as {
        text?: unknown;
        sources?: unknown;
        items?: unknown;
      };
      if (parsed && typeof parsed === "object") {
        const sources = Array.isArray(parsed.sources)
          ? parsed.sources.filter((item): item is StepMediaItem => Boolean(item && typeof item === "object"))
          : [];
        const items = Array.isArray(parsed.items)
          ? parsed.items.filter((item): item is StepMediaItem => Boolean(item && typeof item === "object"))
          : [];
        return {
          text: typeof parsed.text === "string" ? parsed.text : "",
          sources,
          items,
        };
      }
    } catch {
      /* plain text */
    }
  }
  return { text: content, sources: [], items: [] };
}

function MediaGrid({ items, emptyLabel }: { items: StepMediaItem[]; emptyLabel?: string }) {
  if (items.length === 0) {
    return emptyLabel ? (
      <p className="text-[length:var(--text-xs)] text-muted-foreground">{emptyLabel}</p>
    ) : null;
  }
  return (
    <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {items.map((item, index) => {
        const key = `${item.url || item.title || "item"}-${index}`;
        const body = (
          <>
            {item.image ? (
              <img
                src={item.image}
                alt={item.title || "来源图片"}
                loading="lazy"
                referrerPolicy="no-referrer"
                className="h-20 w-20 shrink-0 rounded-[var(--radius-sm)] object-cover bg-muted"
              />
            ) : (
              <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-muted/50 text-[length:var(--text-xs)] text-muted-foreground">
                无图
              </div>
            )}
            <div className="min-w-0 flex-1 space-y-1">
              <p className="line-clamp-2 text-[length:var(--text-sm)] font-medium text-foreground">
                {item.title || item.url || "未命名来源"}
              </p>
              {item.platform || item.price ? (
                <p className="text-[length:var(--text-xs)] text-muted-foreground">
                  {[item.platform, item.price].filter(Boolean).join(" · ")}
                </p>
              ) : null}
              {item.snippet ? (
                <p className="line-clamp-2 text-[length:var(--text-xs)] text-muted-foreground">
                  {item.snippet}
                </p>
              ) : null}
              {item.url ? (
                <p className="truncate text-[length:var(--text-xs)] text-primary/80">{item.url}</p>
              ) : null}
            </div>
          </>
        );
        return (
          <li key={key}>
            {item.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noreferrer"
                className="flex gap-3 rounded-[var(--radius-md)] p-1.5 transition-colors hover:bg-muted/40"
              >
                {body}
              </a>
            ) : (
              <div className="flex gap-3 p-1.5">{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function StepRow({ step }: { step: AgentRunStep }) {
  const payload = useMemo(() => parseStepPayload(step.content), [step.content]);
  const hasMedia = payload.sources.length > 0 || payload.items.length > 0;
  const hasBody = Boolean(
    step.detail || step.content || step.errorKind || step.status === "running" || hasMedia,
  );
  const [open, setOpen] = useState(
    step.status === "running" || Boolean(step.content) || Boolean(step.detail),
  );
  const title = step.label || nodeLabel(step.node);

  useEffect(() => {
    if (step.status === "running" || step.content || step.detail) {
      setOpen(true);
    }
  }, [step.status, step.content, step.detail]);

  return (
    <div className="border-b border-border/50 last:border-b-0">
      <button
        type="button"
        className="flex w-full items-center gap-2 py-2.5 text-left transition-colors hover:bg-muted/30"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <StatusIcon status={step.status} />
        <span className="min-w-0 flex-1 truncate text-[length:var(--text-sm)] font-medium text-foreground">
          {title}
        </span>
        <span className="hidden shrink-0 text-[length:var(--text-xs)] text-muted-foreground sm:inline">
          {nodeLabel(step.node)}
          {hasMedia ? ` · ${payload.sources.length + payload.items.length} 条` : ""}
          {step.model ? ` · ${step.model}` : ""}
        </span>
        {hasBody ? (
          open ? (
            <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          ) : (
            <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden />
          )
        ) : null}
      </button>
      {open && hasBody ? (
        <div className="space-y-3 pb-3 pl-6">
          {step.detail ? (
            <p className="text-[length:var(--text-xs)] text-muted-foreground">{step.detail}</p>
          ) : null}
          {step.errorKind ? (
            <p className="text-[length:var(--text-xs)] text-destructive">错误类型：{step.errorKind}</p>
          ) : null}
          {payload.sources.length > 0 ? (
            <div className="space-y-2">
              <p className="text-[length:var(--text-xs)] font-medium text-muted-foreground">
                调研网页（{payload.sources.length}）
              </p>
              <MediaGrid items={payload.sources} />
            </div>
          ) : null}
          {payload.items.length > 0 ? (
            <div className="space-y-2">
              <p className="text-[length:var(--text-xs)] font-medium text-muted-foreground">
                商品结果（{payload.items.length}）
              </p>
              <MediaGrid items={payload.items} />
            </div>
          ) : null}
          {payload.text ? (
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words font-sans text-[length:var(--text-xs)] leading-relaxed text-foreground/90">
              {payload.text}
            </pre>
          ) : null}
          {!payload.text && !hasMedia && step.status === "running" ? (
            <p className="text-[length:var(--text-xs)] text-muted-foreground">
              模型思考中，完成后会展示本步输出…
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** 比价选品页。 */
export function DiscoveryPage() {
  const {
    draft,
    setDraft,
    session,
    ready,
    busy,
    error,
    start,
    pause,
    resume,
    cancel,
    clear,
  } = usePriceCompareRun();

  const [panelOpen, setPanelOpen] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);
  const run = session?.run ?? null;
  const steps = useMemo(() => {
    const list = [...(run?.steps ?? [])];
    list.sort((a, b) => a.index - b.index);
    return list;
  }, [run?.steps]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps.length, run?.reply, run?.state, session?.prompt]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void start();
    }
  }

  const state = run?.state ?? (session ? "starting" : "idle");
  const canCompose = !busy;
  const canResumeFromStore =
    run?.state === "interrupted" || run?.state === "failed" || run?.state === "cancelled";

  return (
    <PageScaffold
      title="比价选品"
      subtitle="输入需求，Agent 按调研 → 规划 → 爬虫核验流程思考并输出选品建议"
      scroll={false}
      fill
      containerPadding="sm"
      className="min-h-0"
      extra={
        <IconButton
          label={panelOpen ? "收起换模配置" : "展开换模配置"}
          onClick={() => setPanelOpen((open) => !open)}
        >
          {panelOpen ? (
            <PanelRightClose className="size-4" aria-hidden />
          ) : (
            <PanelRightOpen className="size-4" aria-hidden />
          )}
        </IconButton>
      }
    >
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <ScrollArea className="min-h-0 flex-1">
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-1 py-4 sm:px-2">
              {!ready ? (
                <div className="flex items-center justify-center gap-2 py-16 text-[length:var(--text-sm)] text-muted-foreground">
                  <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
                  正在恢复上次会话…
                </div>
              ) : !session ? (
                <div className="flex flex-col items-center gap-5 py-10 text-center">
                  <TrendingUp className="size-8 text-primary/80" aria-hidden />
                  <div className="space-y-2">
                    <h2 className="text-[length:var(--text-base)] font-medium text-foreground">
                      描述你想找的套利机会
                    </h2>
                    <p className="max-w-md text-[length:var(--text-sm)] text-muted-foreground">
                      像和 Agent 对话一样输入一段文字。系统会联网调研、规划关键词，并对照闲鱼与
                      1688 价差后给出建议。会话会自动保存，下次进入可继续。
                    </p>
                  </div>
                  <div className="flex w-full max-w-xl flex-col gap-1">
                    {PROMPT_SUGGESTIONS.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        className="rounded-[var(--radius-md)] px-3 py-2 text-left text-[length:var(--text-sm)] text-muted-foreground transition-colors hover:bg-muted/40 hover:text-foreground"
                        onClick={() => setDraft(suggestion)}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  <article className="ml-auto max-w-[85%] space-y-1">
                    <p className="text-right text-[length:var(--text-xs)] text-muted-foreground">你</p>
                    <p className="whitespace-pre-wrap break-words text-[length:var(--text-sm)] leading-relaxed text-foreground">
                      {session.prompt}
                    </p>
                  </article>

                  <section className="space-y-3">
                    <div className="flex items-center gap-2 text-[length:var(--text-xs)] text-muted-foreground">
                      <Bot className="size-3.5" aria-hidden />
                      <span>Agent</span>
                      <span className={statusTone(state)}>· {state}</span>
                    </div>

                    {steps.length === 0 && busy ? (
                      <div className="flex items-center gap-2 py-3 text-[length:var(--text-sm)] text-muted-foreground">
                        <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
                        正在启动比价图…
                      </div>
                    ) : null}

                    <div>
                      {steps.map((step) => (
                        <StepRow key={`${step.id}-${step.index}-${step.status}`} step={step} />
                      ))}
                    </div>

                    {run?.reply ? (
                      <article className="space-y-2 pt-2">
                        <div className="flex items-center gap-2 text-[length:var(--text-xs)] text-muted-foreground">
                          <Bot className="size-3.5" aria-hidden />
                          <span>选品结论</span>
                        </div>
                        <p className="whitespace-pre-wrap break-words text-[length:var(--text-sm)] leading-relaxed text-foreground">
                          {run.reply}
                        </p>
                      </article>
                    ) : null}

                    {run?.error ? (
                      <p className="text-[length:var(--text-sm)] text-destructive">
                        {run.error}
                        {run.failedNode ? `（节点：${nodeLabel(run.failedNode)}）` : null}
                      </p>
                    ) : null}
                  </section>
                </>
              )}
              <div ref={endRef} />
            </div>
          </ScrollArea>

          <footer className="border-t border-border/60 px-1 py-3 sm:px-2">
            {error ? (
              <p className="mb-2 text-[length:var(--text-xs)] text-destructive">{error}</p>
            ) : null}
            <div className="mx-auto w-full max-w-3xl">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-[length:var(--text-xs)] text-muted-foreground">
                  {busy
                    ? "任务执行中 — 可暂停或取消"
                    : run?.state === "interrupted"
                      ? "上次会话已中断 — 可从断点继续"
                      : "输入需求后开始比价（会话自动保存）"}
                </p>
                <div className="flex items-center gap-1">
                  {busy && run?.state === "running" ? (
                    <Button type="button" variant="ghost" size="sm" onClick={() => void pause()}>
                      <CirclePause className="size-3.5" aria-hidden />
                      暂停
                    </Button>
                  ) : null}
                  {run?.state === "paused" ? (
                    <Button type="button" variant="ghost" size="sm" onClick={() => void resume()}>
                      <Play className="size-3.5" aria-hidden />
                      继续
                    </Button>
                  ) : null}
                  {canResumeFromStore && !busy ? (
                    <Button type="button" variant="ghost" size="sm" onClick={() => void resume()}>
                      <Play className="size-3.5" aria-hidden />
                      从断点继续
                    </Button>
                  ) : null}
                  {busy ? (
                    <Button type="button" variant="ghost" size="sm" onClick={() => void cancel()}>
                      <Square className="size-3.5" aria-hidden />
                      取消
                    </Button>
                  ) : null}
                  {session && !busy ? (
                    <Button type="button" variant="ghost" size="sm" onClick={clear}>
                      新会话
                    </Button>
                  ) : null}
                  <span className="shrink-0 text-[length:var(--text-xs)] text-muted-foreground/70">
                    Ctrl+Enter
                  </span>
                </div>
              </div>
              <Textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="例如：找闲鱼高需求、1688 低价的数码配件套利机会…"
                rows={3}
                disabled={!canCompose && Boolean(session)}
                className="min-h-[4.5rem] resize-none border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
              />
              <div className="mt-2 flex justify-end">
                <AsyncButton
                  size="sm"
                  loading={busy && !run}
                  disabled={!draft.trim() || busy}
                  onClick={() => start()}
                >
                  <Send className="size-3.5" aria-hidden />
                  开始比价
                </AsyncButton>
              </div>
            </div>
          </footer>
        </div>

        {panelOpen ? <FailoverPanel onClose={() => setPanelOpen(false)} /> : null}
      </div>
    </PageScaffold>
  );
}
