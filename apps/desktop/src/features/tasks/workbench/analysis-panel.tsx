/**
 * 右侧分析面板 — Tabs + 结构化结果。
 */

import { useState } from "react";
import { Button, ScrollArea } from "@desk/ui";
import { cn } from "@desk/ui/lib/cn";

import {
  AnalysisSummary,
  PriceDistributionChart,
  PriceSummary,
  PriceTrend,
  PurchaseRecommendation,
} from "../components/analysis/analysis";
import { ProductGrid, ProductTable } from "../components/product/product";
import type { AgentRunState } from "./types";

type TabId = "summary" | "products" | "trend" | "advice";

export function AnalysisWorkbenchPanel({
  run,
  onProductSelect,
}: {
  run: AgentRunState | null;
  onProductSelect: (id: string) => void;
}) {
  const [tab, setTab] = useState<TabId>("summary");
  const analysis = run?.analysis;
  const products = run?.products ?? [];
  const recommended = analysis?.recommendation?.productId
    ? products.find((item) => item.id === analysis.recommendation!.productId) ?? null
    : null;

  const tabs: { id: TabId; label: string }[] = [
    { id: "summary", label: "分析结果" },
    { id: "products", label: `商品列表${products.length ? ` (${products.length})` : ""}` },
    { id: "trend", label: "价格趋势" },
    { id: "advice", label: "购买建议" },
  ];

  return (
    <aside className="flex h-full min-w-[320px] flex-1 flex-col overflow-hidden border-l border-border/60 bg-card">
      <div className="shrink-0 border-b border-border/60 px-4 py-3">
        <p className="text-[length:var(--text-sm)] font-semibold text-foreground">Analysis Result</p>
        <p className="mt-0.5 text-[length:var(--text-xs)] text-muted-foreground">
          {run ? `已发现 ${products.length} 个商品` : "等待 Agent 执行"}
        </p>
      </div>

      <div className="flex shrink-0 gap-1 overflow-x-auto border-b border-border/60 px-3" role="tablist">
        {tabs.map((item) => (
          <Button
            key={item.id}
            type="button"
            size="sm"
            variant="ghost"
            role="tab"
            aria-selected={tab === item.id}
            className={cn(
              "shrink-0 rounded-none border-b-2 border-transparent px-2",
              tab === item.id && "border-primary text-foreground",
            )}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </Button>
        ))}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-4">
          {tab === "summary" ? (
            <>
              {analysis?.priceBuckets?.length ? <PriceSummary buckets={analysis.priceBuckets} /> : null}
              {analysis?.distribution?.length ? (
                <PriceDistributionChart distribution={analysis.distribution} />
              ) : null}
              {analysis?.summary?.length ? (
                <AnalysisSummary
                  summary={analysis.summary}
                  recommendedRange={analysis.recommendedRange}
                />
              ) : null}
              {!analysis ? (
                <p className="py-8 text-center text-[length:var(--text-sm)] text-muted-foreground">
                  分析进行中…
                </p>
              ) : null}
              {products.length > 0 ? (
                <div>
                  <p className="mb-2 text-[length:var(--text-sm)] font-medium">热门商品</p>
                  <ProductGrid
                    products={products.slice(0, 4)}
                    onSelect={(product) => onProductSelect(product.id)}
                  />
                </div>
              ) : null}
            </>
          ) : null}

          {tab === "products" ? (
            <ProductTable products={products} onSelect={(product) => onProductSelect(product.id)} />
          ) : null}

          {tab === "trend" ? (
            <PriceTrend distribution={analysis?.distribution ?? []} />
          ) : null}

          {tab === "advice" ? (
            <PurchaseRecommendation product={recommended} analysis={analysis ?? null} />
          ) : null}
        </div>
      </ScrollArea>
    </aside>
  );
}
