/**
 * 1688 比价结果：来源商品、价格对比图与候选依据。
 * 只消费后端 comparison 快照，不在前端推断平台或推荐原因。
 */

import {
  ArrowRight,
  BadgeCheck,
  ExternalLink,
  Factory,
  PackageSearch,
  Star,
  TrendingUp,
} from "lucide-react";
import type {
  AgentWorkComparisonItemView,
  AgentWorkComparisonSourceView,
  AgentWorkComparisonView,
} from "@v2/contracts/ai-work";
import { Avatar, AvatarFallback, AvatarImage } from "@v2/ui-primitives/avatar";
import { Badge } from "@v2/ui-primitives/badge";
import { cn } from "@v2/ui-primitives/utils";
import { openProductInBrowserTab } from "@/lib/product-preview";

const PLATFORM_LABEL: Record<string, string> = {
  xianyu: "闲鱼",
  xiaohongshu: "小红书",
  ali1688: "1688",
  taobao: "淘宝",
  tmall: "天猫",
  source: "来源",
};

const BAR_COLORS = [
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-cyan-500",
  "bg-orange-500",
];

function priceValue(price: string | null | undefined): number | null {
  const match = String(price ?? "")
    .replace(/,/g, "")
    .match(/\d+(?:\.\d+)?/);
  if (!match) return null;
  const value = Number(match[0]);
  return Number.isFinite(value) ? value : null;
}

function formatCount(value: number | null | undefined): string {
  if (value == null) return "未返回";
  if (value >= 10000) return `${(value / 10000).toFixed(value >= 100000 ? 0 : 1)}万`;
  return String(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value == null) return "未返回";
  const unit = value > 1 ? value / 100 : value;
  return `${Math.round(unit * 100)}%`;
}

function formatScore(value: number | null | undefined): string {
  if (value == null) return "未返回";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function platformLabel(value: string): string {
  return PLATFORM_LABEL[value] || value || "来源";
}

function openExternal(url: string | null | undefined): void {
  const target = (url || "").trim();
  if (target) void openProductInBrowserTab(target);
}

function PriceChart({ comparison }: { comparison: AgentWorkComparisonView }) {
  const sourcePrice = priceValue(comparison.source.price);
  const rows = [
    ...(sourcePrice != null
      ? [
          {
            key: "source",
            label: platformLabel(comparison.source.platform),
            price: sourcePrice,
            value: comparison.source.price || "",
            source: true,
          },
        ]
      : []),
    ...comparison.items.map((item, index) => ({
      key: item.id,
      label: `1688 · ${String.fromCharCode(65 + index)}`,
      price: priceValue(item.price),
      value: item.price,
      source: false,
    })),
  ].filter((row): row is typeof row & { price: number } => row.price != null);

  if (rows.length === 0) {
    return (
      <section className="border-b border-border/70 px-4 py-4">
        <p className="text-xs text-muted-foreground">价格字段未返回，暂时无法绘图。</p>
      </section>
    );
  }

  const max = Math.max(...rows.map((row) => row.price));
  return (
    <section className="border-b border-border/70 px-4 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-xs font-semibold text-foreground">价格对比</h3>
          <p className="text-[11px] text-muted-foreground">越短越好；单位以页面返回价格为准</p>
        </div>
        <Badge variant="outline">{rows.length} 个报价</Badge>
      </div>
      <div className="space-y-3">
        {rows.map((row, index) => (
          <div key={row.key} className="grid grid-cols-[64px_minmax(0,1fr)_auto] items-center gap-3">
            <span className="truncate text-[11px] text-muted-foreground">{row.label}</span>
            <div className="h-2.5 overflow-hidden rounded-sm bg-muted">
              <div
                role="img"
                aria-label={`${row.label} 价格 ${row.value}`}
                className={cn(
                  "h-full rounded-sm",
                  row.source
                    ? "bg-sky-500"
                    : BAR_COLORS[(index - (sourcePrice != null ? 1 : 0)) % BAR_COLORS.length],
                )}
                style={{ width: `${Math.max(8, (row.price / max) * 100)}%` }}
              />
            </div>
            <span className="min-w-12 text-right text-xs font-semibold tabular-nums text-foreground">
              {row.value}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function SourceSummary({ source }: { source: AgentWorkComparisonSourceView }) {
  return (
    <section className="border-b border-border/70 px-4 py-4">
      <div className="mb-3 flex items-center gap-2">
        <PackageSearch className="size-3.5 text-sky-600" />
        <h3 className="text-xs font-semibold text-foreground">来源商品</h3>
        <Badge variant="secondary">{platformLabel(source.platform)}</Badge>
      </div>
      <div className="flex min-w-0 gap-3">
        <Avatar className="size-14 shrink-0 rounded-md after:rounded-md">
          {source.image_url ? (
            <AvatarImage src={source.image_url} alt="" className="rounded-md object-cover" />
          ) : null}
          <AvatarFallback className="rounded-md text-[10px]">来源</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-xs font-medium leading-snug text-foreground">
            {source.title || "来源标题未提供"}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
            <span className="font-semibold text-foreground">{source.price || "价格未提供"}</span>
            {source.seller ? <span>{source.seller}</span> : null}
          </div>
        </div>
        {source.url ? (
          <button
            type="button"
            aria-label="打开来源商品"
            className="self-start rounded-md p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground"
            onClick={() => openExternal(source.url)}
          >
            <ExternalLink className="size-3.5" />
          </button>
        ) : null}
      </div>
    </section>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0 rounded-md bg-muted/35 px-2.5 py-2">
      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <p className="mt-1 truncate text-xs font-medium text-foreground">{value}</p>
    </div>
  );
}

function OfferRow({
  item,
  index,
}: {
  item: AgentWorkComparisonItemView;
  index: number;
}) {
  return (
    <article className="border-b border-border/70 px-4 py-4 last:border-b-0">
      <div className="flex min-w-0 gap-3">
        <Avatar className="size-16 shrink-0 rounded-md after:rounded-md">
          {item.image_url ? (
            <AvatarImage src={item.image_url} alt="" className="rounded-md object-cover" />
          ) : null}
          <AvatarFallback className="rounded-md text-[10px]">1688</AvatarFallback>
        </Avatar>

        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-start gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                <span>方案 {String.fromCharCode(65 + index)}</span>
                {item.round ? <span>第 {item.round} 轮</span> : null}
              </div>
              <h3 className="mt-0.5 line-clamp-2 text-xs font-medium leading-snug text-foreground">
                {item.title || "1688 同款"}
              </h3>
            </div>
            <button
              type="button"
              aria-label="打开 1688 商品"
              disabled={!item.product_url}
              className="shrink-0 rounded-md p-1.5 text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:opacity-40"
              onClick={() => openExternal(item.product_url)}
            >
              <ExternalLink className="size-3.5" />
            </button>
          </div>

          <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-lg font-semibold tracking-tight text-foreground">
              {item.price || "—"}
            </span>
            {item.compare_score != null ? (
              <span className="text-[11px] text-muted-foreground">
                综合分 {item.compare_score.toFixed(1)}
              </span>
            ) : null}
          </div>

          {item.compare_reasons.length > 0 ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {item.compare_reasons.map((reason) => (
                <Badge key={reason} variant="outline" className="h-auto py-0.5 text-[10px]">
                  <BadgeCheck className="size-2.5" />
                  {reason}
                </Badge>
              ))}
            </div>
          ) : item.compare_label ? (
            <Badge variant="outline" className="mt-2">
              {item.compare_label}
            </Badge>
          ) : null}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Metric
          icon={<Factory className="size-3" />}
          label="供应商"
          value={item.seller || "未返回"}
        />
        <Metric
          icon={<Star className="size-3" />}
          label="商家评分"
          value={formatScore(item.merchant_rating)}
        />
        <Metric
          icon={<TrendingUp className="size-3" />}
          label="成交"
          value={formatCount(item.sold_count)}
        />
        <Metric
          icon={<BadgeCheck className="size-3" />}
          label="同款匹配"
          value={formatPercent(item.similarity_score)}
        />
        <Metric
          icon={<BadgeCheck className="size-3" />}
          label="严选指数"
          value={formatScore(item.yx_index)}
        />
        <Metric
          icon={<PackageSearch className="size-3" />}
          label="起订 / 库存"
          value={`${item.quantity_begin ?? "—"} / ${formatCount(item.stock_amount)}`}
        />
      </div>
    </article>
  );
}

/** 右侧比价面板。 */
export function ComparisonResults({ comparison }: { comparison: AgentWorkComparisonView }) {
  const sourcePrice = priceValue(comparison.source.price);
  const offerPrices = comparison.items
    .map((item) => priceValue(item.price))
    .filter((value): value is number => value != null);
  const lowest = offerPrices.length > 0 ? Math.min(...offerPrices) : null;
  const spread =
    sourcePrice != null && lowest != null && sourcePrice > 0
      ? Math.max(0, Math.round(((sourcePrice - lowest) / sourcePrice) * 100))
      : null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-border/70 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">1688 货源对比</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {comparison.rounds} 轮找货 · {comparison.total_candidates} 次候选命中
            {spread != null ? ` · 最低价差 ${spread}%` : ""}
          </p>
        </div>
        <Badge className={cn("shrink-0 border-transparent", comparison.status.badge_class)}>
          {comparison.status.label}
        </Badge>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {(comparison.queries?.length ?? 0) > 0 ? (
          <div className="flex flex-wrap gap-1.5 border-b border-border/70 px-4 py-2.5">
            <span className="mr-1 text-[10px] leading-5 text-muted-foreground">检索轮次</span>
            {(comparison.queries ?? []).map((query, index) => (
              <Badge
                key={`${query}-${index}`}
                variant="outline"
                className="max-w-full gap-1 py-0.5 text-[10px]"
                title={query}
              >
                <span className="shrink-0">{index + 1}</span>
                <span className="max-w-40 truncate">{query}</span>
              </Badge>
            ))}
          </div>
        ) : null}
        <SourceSummary source={comparison.source} />
        <div className="flex items-center gap-2 border-b border-border/70 bg-muted/25 px-4 py-2 text-[11px] text-muted-foreground">
          <span>来源商品</span>
          <ArrowRight className="size-3" />
          <span>1688 同款报价</span>
        </div>
        <PriceChart comparison={comparison} />

        <section>
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <div>
              <h3 className="text-xs font-semibold text-foreground">候选依据</h3>
              <p className="text-[11px] text-muted-foreground">按价格、销量、匹配度和严选指数筛选</p>
            </div>
            <Badge variant="outline">{comparison.items.length} 款</Badge>
          </div>
          {comparison.items.length > 0 ? (
            comparison.items.map((item, index) => (
              <OfferRow key={item.id} item={item} index={index} />
            ))
          ) : (
            <p className="px-4 pb-6 text-xs text-muted-foreground">没有可用的 1688 候选。</p>
          )}
        </section>
      </div>
    </div>
  );
}
