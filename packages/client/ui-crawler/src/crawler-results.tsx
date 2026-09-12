import { ExternalLink, Loader2 } from "lucide-react";
import type { CrawlProductItem } from "@v2/contracts/crawler";
import { Button } from "@v2/ui-primitives/button";
import { Card, CardContent } from "@v2/ui-primitives/card";
import { cn } from "@v2/ui-primitives/utils";

interface CrawlerResultsProps {
  items: CrawlProductItem[];
  loading?: boolean;
  emptyHint?: string;
}

export function CrawlerResults({ items, loading, emptyHint }: CrawlerResultsProps) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
        <Loader2 className="size-8 animate-spin" />
        <p className="text-sm">正在爬取商品…</p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border px-6 py-16 text-center">
        <p className="text-sm text-muted-foreground">
          {emptyHint ?? "输入关键词后点击「开始爬取」查看商品"}
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <Card key={item.id} className="transition hover:border-primary/40">
          <CardContent className="flex h-full flex-col gap-3 p-4">
            <div className="flex gap-3">
              <div className="flex size-16 shrink-0 items-center justify-center rounded-lg bg-muted text-xs text-muted-foreground">
                图
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="line-clamp-2 text-sm font-medium leading-snug">{item.title}</p>
                <p className="text-base font-semibold text-foreground">{item.price}</p>
              </div>
            </div>
            <div className="mt-auto space-y-1 text-xs text-muted-foreground">
              {item.seller ? <p className="truncate">卖家 {item.seller}</p> : null}
              {item.location ? <p className="truncate">地区 {item.location}</p> : null}
            </div>
            <Button variant="outline" size="sm" className="w-full" disabled>
              <ExternalLink className="size-3.5" />
              查看详情
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

interface CrawlerStatusBannerProps {
  label: string;
  hint?: string | null;
  badgeClass: string;
}

export function CrawlerStatusBanner({ label, hint, badgeClass }: CrawlerStatusBannerProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2">
      <span className="text-sm text-muted-foreground">任务状态</span>
      <div className="flex flex-col items-end gap-0.5">
        <span className={cn("rounded-full px-2 py-0.5 text-xs", badgeClass)}>{label}</span>
        {hint ? <span className="text-xs text-orange-700">{hint}</span> : null}
      </div>
    </div>
  );
}
