/**
 * 工具/页面块：标题用后端 label；展开区只展示 url / 截图 / 商品，不解析平台。
 */

import { ExternalLink, Globe, Loader2, Lock, Radio } from "lucide-react";
import type { AgentWorkProductItem, AgentWorkStepView } from "@v2/contracts/ai-work";
import { Badge } from "@v2/ui-primitives/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@v2/ui-primitives/avatar";
import { openProductPreview } from "@v2/ui-crawler/product-preview";
import { Collapse } from "../Collapse";
import { CodexActivityIndicator } from "../ThinkingOrb";

export interface StepBlockProps {
  step: AgentWorkStepView;
  pageUrl?: string | null;
  products?: AgentWorkProductItem[];
  selected?: boolean;
  onSelect?: (step: AgentWorkStepView) => void;
}

function isRunning(state: string): boolean {
  return state === "running" || state === "browsing" || state === "pending";
}

function ProductStrip({ items }: { items: AgentWorkProductItem[] }) {
  if (items.length === 0) return null;

  const openItem = (item: AgentWorkProductItem) => {
    openProductPreview(item);
  };

  return (
    <div className="overflow-x-auto pt-2">
      <div className="flex w-max gap-2 pr-2">
        {items.map((item) => {
          return (
            <button
              key={item.id}
              type="button"
              className="w-[132px] shrink-0 cursor-pointer rounded-md border border-border/70 bg-background p-2 text-left transition hover:border-primary/40"
              onClick={(event) => {
                event.stopPropagation();
                openItem(item);
              }}
            >
              <Avatar className="h-[72px] w-full rounded-md after:rounded-md">
                {item.image_url ? (
                  <AvatarImage src={item.image_url} alt="" className="rounded-md object-cover" />
                ) : null}
                <AvatarFallback className="rounded-md text-[10px]">图</AvatarFallback>
              </Avatar>
              <p className="mt-1.5 line-clamp-2 h-7 text-[11px] font-medium leading-[14px]">
                {item.title}
              </p>
              <p className="truncate text-xs font-semibold">{item.price || "—"}</p>
              <p className="mt-0.5 truncate text-[10px] text-primary">查看详情</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PagePreview({
  page,
  products,
}: {
  page: NonNullable<AgentWorkStepView["page"]>;
  products: AgentWorkProductItem[];
}) {
  const hasShot = Boolean(page.screenshot_url);
  const live = Boolean(page.loading && hasShot);

  return (
    <div className="overflow-hidden rounded-md border border-border/70 bg-background">
      <div className="flex items-center gap-2 border-b border-border/70 bg-muted/30 px-2.5 py-1.5">
        <Lock className="size-3 shrink-0 text-muted-foreground" />
        {page.url ? (
          <a
            href={page.url}
            target="_blank"
            rel="noopener noreferrer"
            className="min-w-0 flex-1 truncate font-mono text-[11px] text-foreground/80 hover:underline"
            onClick={(event) => event.stopPropagation()}
          >
            {page.url}
          </a>
        ) : (
          <span className="min-w-0 flex-1 truncate font-mono text-[11px]">…</span>
        )}
        {live ? (
          <Badge variant="destructive" className="gap-1 shrink-0 px-1.5 py-0 text-[10px]">
            <Radio className="size-2.5" />
            LIVE
          </Badge>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-2 border-b border-border/60 px-2.5 py-1.5 text-[11px] text-muted-foreground">
        <div className="flex min-w-0 items-center gap-1.5">
          <Globe className="size-3 shrink-0" />
          <span className="truncate font-medium text-foreground">{page.title}</span>
        </div>
        {page.focus_label ? <Badge variant="secondary">{page.focus_label}</Badge> : null}
      </div>
      <div className="relative max-h-80 overflow-hidden bg-black/5">
        {hasShot ? (
          <img
            src={page.screenshot_url!}
            alt={page.title}
            className="w-full object-contain object-top"
            decoding="async"
          />
        ) : (
          <div className="space-y-2 p-4">
            <div className="h-8 w-2/5 rounded-md bg-muted" />
            <div className="grid grid-cols-2 gap-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="aspect-[4/3] rounded-md bg-muted" />
              ))}
            </div>
            <p className="text-center text-[11px] text-muted-foreground">
              {page.title}
              {page.focus_label ? ` · ${page.focus_label}` : ""}
            </p>
          </div>
        )}
        {page.loading ? (
          <Badge
            variant="outline"
            className="absolute right-2 bottom-2 gap-1.5 bg-background/95 py-1 pr-2.5 pl-2 shadow-sm"
          >
            <Loader2 className="size-3 animate-spin text-sky-600" />
            {page.focus_label || (live ? "直播中…" : "打开中…")}
          </Badge>
        ) : null}
      </div>
      <ProductStrip items={products} />
    </div>
  );
}

export function StepBlock({
  step,
  pageUrl = null,
  products = [],
  onSelect,
}: StepBlockProps) {
  const running = isRunning(step.status.state);
  const page = step.page;
  const linkUrl = page?.url || pageUrl || null;
  const showPage = Boolean(page?.screenshot_url || page?.url || page?.loading);
  const showProducts = products.length > 0 && !showPage;

  const title = (
    <span className="flex min-w-0 flex-1 items-center gap-2">
      {running ? (
        <CodexActivityIndicator className="w-3.5 shrink-0 text-[13px] text-sky-600" />
      ) : (
        <span className="w-3.5 shrink-0 text-center text-muted-foreground/70">•</span>
      )}
      <span className="min-w-0 truncate">
        <span className="font-medium text-foreground/90">{step.label}</span>
        {step.hint ? <span className="text-muted-foreground"> · {step.hint}</span> : null}
      </span>
    </span>
  );

  const trailing = (
    <span
      className={
        step.status.state === "error"
          ? "shrink-0 text-[11px] text-destructive"
          : "shrink-0 text-[11px] text-muted-foreground"
      }
    >
      {step.status.label}
    </span>
  );

  const body = showPage && page ? (
    <PagePreview page={page} products={products} />
  ) : showProducts ? (
    <ProductStrip items={products} />
  ) : linkUrl ? (
    <a
      href={linkUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex max-w-full items-center gap-1 text-[11px] text-muted-foreground hover:underline"
    >
      <ExternalLink className="size-3 shrink-0" />
      <span className="truncate">{linkUrl}</span>
    </a>
  ) : null;

  return (
    <div onClick={() => onSelect?.(step)}>
      <Collapse
        title={title}
        trailing={trailing}
        defaultOpen={Boolean(body)}
        // 跑着强制展开；结束后不强制收起，方便回看截图
        lifecycleOpen={running && Boolean(body) ? true : undefined}
      >
        {body}
      </Collapse>
    </div>
  );
}
