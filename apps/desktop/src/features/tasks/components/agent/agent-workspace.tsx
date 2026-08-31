import { useState } from "react";
import {
  Button,
  Card,
  CardContent,
  Progress,
  ScrollArea,
} from "@desk/ui";
import {
  Check,
  ChevronDown,
  ChevronRight,
  Circle,
  Loader2,
  Search,
  Terminal,
  X,
} from "@desk/ui/icons";

import { ProductGrid } from "../product/product";
import type { AgentStep, AgentStepStatus, AgentToolCall, Product } from "../../workbench/types";

function stepIcon(status: AgentStepStatus) {
  if (status === "running") {
    return <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden />;
  }
  if (status === "success") {
    return <Check className="size-3.5 text-emerald-600" aria-hidden />;
  }
  if (status === "error") {
    return <X className="size-3.5 text-destructive" aria-hidden />;
  }
  return <Circle className="size-3.5 text-muted-foreground/50" aria-hidden />;
}

function AgentStepRow({ step }: { step: AgentStep }) {
  const [open, setOpen] = useState(step.status === "running");
  const hasBody = Boolean(step.description || step.result);

  return (
    <div className="flex gap-3">
      <div className="flex w-5 flex-col items-center">
        <div className="mt-0.5">{stepIcon(step.status)}</div>
        <div className="mt-1 w-px flex-1 bg-border/70" />
      </div>
      <div className="min-w-0 flex-1 pb-4">
        <button
          type="button"
          className="flex w-full items-center gap-2 text-left"
          onClick={() => hasBody && setOpen((value) => !value)}
        >
          <span className="text-[length:var(--text-sm)] font-medium text-foreground">{step.title}</span>
          {step.duration != null ? (
            <span className="text-[length:var(--text-xs)] text-muted-foreground">{step.duration}s</span>
          ) : null}
          {hasBody ? (
            open ? (
              <ChevronDown className="ml-auto size-3.5 text-muted-foreground" />
            ) : (
              <ChevronRight className="ml-auto size-3.5 text-muted-foreground" />
            )
          ) : null}
        </button>
        {step.description ? (
          <p className="mt-1 text-[length:var(--text-xs)] text-muted-foreground">{step.description}</p>
        ) : null}
        {open && step.result != null ? (
          <pre className="mt-2 overflow-x-auto rounded-[var(--radius-md)] bg-muted/30 p-2 text-[length:var(--text-xs)] text-muted-foreground">
            {JSON.stringify(step.result, null, 2)}
          </pre>
        ) : null}
      </div>
    </div>
  );
}

export function AgentToolCallCard({ tool }: { tool: AgentToolCall }) {
  const [open, setOpen] = useState(tool.status === "running");
  const args = tool.args as Record<string, unknown>;

  return (
    <Card className="border-border/60 shadow-none">
      <CardContent className="p-3">
        <button
          type="button"
          className="flex w-full items-center gap-2 text-left"
          onClick={() => setOpen((value) => !value)}
        >
          <Terminal className="size-3.5 shrink-0 text-muted-foreground" />
          <span className="text-[length:var(--text-sm)] font-medium">{tool.tool}</span>
          <span className="text-[length:var(--text-xs)] text-muted-foreground">
            {tool.status === "running" ? "执行中…" : tool.duration ? `${(tool.duration / 1000).toFixed(1)}s` : "完成"}
          </span>
          {open ? (
            <ChevronDown className="ml-auto size-3.5" />
          ) : (
            <ChevronRight className="ml-auto size-3.5" />
          )}
        </button>
        {open ? (
          <div className="mt-2 space-y-2 text-[length:var(--text-xs)] text-muted-foreground">
            {args.keyword ? <p>关键词：{String(args.keyword)}</p> : null}
            {args.platform ? <p>平台：{String(args.platform)}</p> : null}
            {tool.result != null ? (
              <p>
                结果：
                {typeof tool.result === "object" && tool.result !== null && "count" in tool.result
                  ? ` ${String((tool.result as { count: number }).count)} 个商品`
                  : JSON.stringify(tool.result)}
              </p>
            ) : null}
            {tool.error ? <p className="text-destructive">{tool.error}</p> : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function AgentTimeline({
  steps,
  toolCalls,
  products,
  progress,
  progressMessage,
  onProductSelect,
}: {
  steps: AgentStep[];
  toolCalls: AgentToolCall[];
  products: Product[];
  progress: number;
  progressMessage?: string;
  onProductSelect?: (product: Product) => void;
}) {
  const [open, setOpen] = useState(true);

  if (steps.length === 0 && toolCalls.length === 0 && products.length === 0) {
    return null;
  }

  return (
    <section className="w-full">
      <button
        type="button"
        className="mb-2 flex w-full items-center gap-2 border-b border-border/60 pb-2 text-left"
        onClick={() => setOpen((value) => !value)}
      >
        <Search className="size-4 text-muted-foreground" />
        <span className="text-[length:var(--text-sm)] font-semibold text-foreground">思考过程</span>
        {progressMessage ? (
          <span className="truncate text-[length:var(--text-xs)] text-muted-foreground">{progressMessage}</span>
        ) : null}
        <ChevronDown
          className={`ml-auto size-4 text-muted-foreground transition-transform ${open ? "" : "-rotate-90"}`}
        />
      </button>

      {open ? (
        <div className="space-y-3">
          {progress > 0 ? (
            <div className="space-y-1">
              <Progress value={progress} className="h-1.5" />
            </div>
          ) : null}

          {steps.map((step) => (
            <AgentStepRow key={step.id} step={step} />
          ))}

          {toolCalls.map((tool) => (
            <AgentToolCallCard key={tool.id} tool={tool} />
          ))}

          {products.length > 0 ? (
            <div>
              <p className="mb-2 text-[length:var(--text-sm)] font-medium text-foreground">
                找到 {products.length} 个相关商品
              </p>
              <ProductGrid products={products.slice(0, 4)} onSelect={onProductSelect} />
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function AgentMessage({ role, content }: { role: "user" | "assistant"; content: string }) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-[22px] bg-primary/10 px-4 py-2.5 text-[length:var(--text-sm)] text-foreground">
          {content}
        </div>
      </div>
    );
  }
  return (
    <div className="text-[length:var(--text-sm)] leading-relaxed text-foreground/90">{content}</div>
  );
}

export function AgentInput({
  disabled,
  running,
  onSend,
  onStop,
}: {
  disabled?: boolean;
  running?: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}) {
  const [draft, setDraft] = useState("");

  const submit = () => {
    if (!draft.trim() || disabled || running) {
      return;
    }
    onSend(draft);
    setDraft("");
  };

  return (
    <div className="shrink-0 border-t border-border/60 bg-card p-4">
      <div className="mx-auto max-w-3xl">
        <div className="rounded-[var(--radius-xl)] border border-border/70 bg-background p-3 shadow-sm">
          <textarea
            className="min-h-[56px] w-full resize-none bg-transparent text-[length:var(--text-sm)] text-foreground outline-none placeholder:text-muted-foreground"
            placeholder="输入你的问题，或让 AI 帮你分析商品…"
            value={draft}
            disabled={disabled || running}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
          />
          <div className="mt-2 flex items-center justify-between gap-2">
            <div className="flex flex-wrap gap-1 text-[length:var(--text-xs)] text-muted-foreground">
              <span className="rounded-full border border-border/60 px-2 py-0.5">附件</span>
              <span className="rounded-full border border-border/60 px-2 py-0.5">深度分析</span>
              <span className="rounded-full border border-border/60 px-2 py-0.5">联网搜索</span>
              <span className="rounded-full border border-border/60 px-2 py-0.5">知识库</span>
            </div>
            {running ? (
              <Button type="button" size="sm" variant="outline" onClick={onStop}>
                停止
              </Button>
            ) : (
              <Button type="button" size="sm" disabled={!draft.trim() || disabled} onClick={submit}>
                发送
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export function AgentWorkspace({
  title,
  messages,
  steps,
  toolCalls,
  products,
  progress,
  progressMessage,
  running,
  onSend,
  onStop,
  onProductSelect,
}: {
  title: string;
  messages: { id: string; role: "user" | "assistant"; content: string }[];
  steps: AgentStep[];
  toolCalls: AgentToolCall[];
  products: Product[];
  progress: number;
  progressMessage?: string;
  running: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  onProductSelect: (product: Product) => void;
}) {
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-border/60 px-5 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-[length:var(--text-sm)] font-semibold text-foreground">{title}</h1>
        </div>
        <div className="flex shrink-0 gap-1">
          {running ? (
            <Button type="button" size="sm" variant="outline" onClick={onStop}>
              停止
            </Button>
          ) : null}
        </div>
      </header>

      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-5 py-4">
          {messages.map((message) => (
            <AgentMessage key={message.id} role={message.role} content={message.content} />
          ))}
          <AgentTimeline
            steps={steps}
            toolCalls={toolCalls}
            products={products}
            progress={progress}
            progressMessage={progressMessage}
            onProductSelect={onProductSelect}
          />
        </div>
      </ScrollArea>

      <AgentInput running={running} onSend={onSend} onStop={onStop} />
    </div>
  );
}
