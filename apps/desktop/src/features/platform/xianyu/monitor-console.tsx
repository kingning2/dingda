/**
 * 监控运行转录渲染 — JSON / Markdown 解析 + agent 式步骤动画。
 */

import { memo, useMemo, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { cn, motion } from "@desk/ui";
import {
  Check,
  CheckCircle,
  Loader2,
  Play,
  Radar,
  ScrollText,
  Search,
  Star,
  Terminal,
  XCircle,
} from "@desk/ui/icons";
import type { MonitorProgressStage, MonitorStepPayload } from "@desk/platform/events";

export type MonitorStepKind = "running" | "success" | "error" | "info";

export function stepKindFor(stage: MonitorProgressStage): MonitorStepKind {
  if (stage === "finished") return "success";
  if (stage === "failed") return "error";
  // 「任务开始运行」是已发生的日志节点，不是进行态；进行态由列表底部 ThinkingDots 表示。
  return "info";
}

export function formatRunTime(rfc3339: string): string {
  const date = new Date(rfc3339);
  if (Number.isNaN(date.getTime())) return rfc3339;
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function StepIcon({
  stage,
  kind,
}: {
  stage: MonitorProgressStage;
  kind: MonitorStepKind;
}) {
  const base = "mt-0.5 size-4 shrink-0";
  if (kind === "error") return <XCircle className={`${base} text-destructive`} />;
  if (kind === "success") return <CheckCircle className={`${base} text-emerald-500`} />;
  if (kind === "running") return <Loader2 className={`${base} animate-spin text-primary`} />;
  switch (stage) {
    case "keywords":
      return <ScrollText className={`${base} text-muted-foreground`} />;
    case "search":
    case "scanned":
      return <Search className={`${base} text-muted-foreground`} />;
    case "decide":
      return <Radar className={`${base} text-muted-foreground`} />;
    case "matched":
      return <Star className={`${base} text-amber-500`} />;
    case "started":
      return <Play className={`${base} text-muted-foreground`} />;
    default:
      return <Check className={`${base} text-muted-foreground`} />;
  }
}

interface JsonToken {
  text: string;
  cls: string;
}

function tokenizeJson(text: string): JsonToken[] {
  const tokens: JsonToken[] = [];
  const re =
    /("(?:[^"\\]|\\.)*"\s*:)|("(?:[^"\\]|\\.)*")|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|(\btrue\b|\bfalse\b|\bnull\b)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      tokens.push({ text: text.slice(last, match.index), cls: "text-muted-foreground" });
    }
    const [full, keyToken, strToken] = match;
    const cls = keyToken
      ? "text-primary"
      : strToken
        ? "text-emerald-600 dark:text-emerald-400"
        : /^-?\d/.test(full)
          ? "text-amber-600 dark:text-amber-400"
          : "text-sky-600 dark:text-sky-400";
    tokens.push({ text: full, cls });
    last = match.index + full.length;
  }
  if (last < text.length) {
    tokens.push({ text: text.slice(last), cls: "text-muted-foreground" });
  }
  return tokens;
}

/** JSON 漂亮打印 + 轻量 token 高亮。 */
export function JsonBlock({ content }: { content: string }) {
  const tokens = useMemo(() => {
    let value: unknown;
    try {
      value = JSON.parse(content);
    } catch {
      return null;
    }
    return tokenizeJson(JSON.stringify(value, null, 2) ?? content);
  }, [content]);

  return (
    <pre className="max-w-full overflow-x-auto rounded-md bg-muted/40 p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-all">
      {tokens === null
        ? content
        : tokens.map((token, index) => (
            <span key={index} className={token.cls}>
              {token.text}
            </span>
          ))}
    </pre>
  );
}

const MARKDOWN_COMPONENTS: Components = {
  p: ({ children }: { children?: ReactNode }) => (
    <p className="my-1 leading-relaxed">{children}</p>
  ),
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-primary underline">
      {children}
    </a>
  ),
  code: ({ children }: { children?: ReactNode }) => (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{children}</code>
  ),
  pre: ({ children }: { children?: ReactNode }) => (
    <pre className="my-1 overflow-x-auto rounded bg-muted/50 p-2 font-mono text-[10px]">
      {children}
    </pre>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="my-1 list-disc space-y-0.5 pl-4">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="my-1 list-decimal space-y-0.5 pl-4">{children}</ol>
  ),
  li: ({ children }: { children?: ReactNode }) => <li>{children}</li>,
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  h1: ({ children }: { children?: ReactNode }) => (
    <h1 className="my-1 text-sm font-semibold">{children}</h1>
  ),
  h2: ({ children }: { children?: ReactNode }) => (
    <h2 className="my-1 text-[13px] font-semibold">{children}</h2>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h3 className="my-1 text-xs font-semibold">{children}</h3>
  ),
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote className="my-1 border-l-2 border-primary/40 pl-2 text-muted-foreground">
      {children}
    </blockquote>
  ),
};

/** Markdown 渲染。 */
export function MarkdownBlock({ content }: { content: string }) {
  return (
    <div className="max-w-none text-xs text-foreground/90">
      <ReactMarkdown components={MARKDOWN_COMPONENTS}>{content}</ReactMarkdown>
    </div>
  );
}

function renderContent(step: MonitorStepPayload) {
  const content = step.content ?? "";
  const kind = step.contentKind ?? "text";
  if (kind === "json") return <JsonBlock content={content} />;
  if (kind === "markdown") return <MarkdownBlock content={content} />;
  return (
    <p className="whitespace-pre-wrap font-mono text-[11px] text-foreground/80">{content}</p>
  );
}

const SPRING = { type: "spring", stiffness: 380, damping: 32 } as const;

function formatToolStepMessage(message: string): string {
  const webSearchMatch = message.match(/web_search\((\{.*\})\)/);
  if (webSearchMatch) {
    try {
      const args = JSON.parse(webSearchMatch[1]) as { query?: string };
      if (args.query?.trim()) {
        return `搜索「${args.query.trim()}」`;
      }
    } catch {
      // fall through
    }
    return "联网搜索";
  }
  return message.replace(/^tool_call\s+\S+\s+→\s*\S+\(/, "").replace(/\)\s*$/, "") || message;
}

/** 单条转录步骤 — 按 role 渲染为气泡 / 工具块 / 流程行。 */
export const TranscriptStep = memo(function TranscriptStep({ step }: { step: MonitorStepPayload }) {
  if (step.role === "user" || step.role === "assistant") {
    const isUser = step.role === "user";
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={SPRING}
        className={cn(
          "rounded-xl border px-3 py-2",
          isUser ? "border-border bg-card" : "border-primary/30 bg-primary/5",
        )}
      >
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-[10px] font-medium tracking-wide",
              isUser ? "text-muted-foreground" : "text-primary",
            )}
          >
            {isUser ? "→ 发送给 AI" : "← AI 返回"}
          </span>
        </div>
        <p className="mt-1 break-words text-xs text-foreground">{step.message}</p>
        {step.content ? (
          <div className="mt-1.5 min-w-0 break-words">
            {renderContent(step)}
          </div>
        ) : null}
      </motion.div>
    );
  }

  if (step.role === "tool") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={SPRING}
        className="rounded-xl border border-dashed border-border bg-muted/20 px-3 py-2"
      >
        <div className="flex items-center gap-1.5">
          <Terminal className="size-3 shrink-0 text-muted-foreground" />
          <span className="truncate text-[10px] font-medium tracking-wide text-muted-foreground">
            联网查询 · {formatToolStepMessage(step.message)}
          </span>
        </div>
        {step.content ? (
          <div className="mt-1.5 min-w-0 break-words">
            {renderContent(step)}
          </div>
        ) : null}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={SPRING}
      className="flex gap-2.5"
    >
      <StepIcon stage={step.stage} kind={stepKindFor(step.stage)} />
      <div className="min-w-0 flex-1 space-y-0.5 pb-1">
        <p className="text-xs text-foreground">{step.message}</p>
        {step.detail ? (
          <p className="break-words text-[10px] text-muted-foreground">{step.detail}</p>
        ) : null}
        {step.summary ? (
          <p className="text-[10px] font-medium text-primary">
            扫描 {step.summary.scanned} · 新增 {step.summary.newItems} · 跳过{" "}
            {step.summary.skipped} · 推荐 {step.summary.recommended}
          </p>
        ) : null}
      </div>
    </motion.div>
  );
});

/** AI 处理中指示（Aceternity 风格三点弹跳）。 */
export function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5 px-1 py-1.5">
      <span className="text-[10px] text-muted-foreground">AI 处理中</span>
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className="size-1.5 rounded-full bg-primary"
          animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 0.8, repeat: Infinity, delay: index * 0.15 }}
        />
      ))}
    </div>
  );
}
