import { Card, CardContent, CardHeader, CardTitle, Progress } from "@desk/ui";

import type { AnalysisData, Product } from "../../workbench/types";

function formatPrice(price: number): string {
  return `¥${price.toLocaleString("zh-CN")}`;
}

export function PriceSummary({ buckets }: { buckets: AnalysisData["priceBuckets"] }) {
  if (buckets.length === 0) {
    return null;
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {buckets.map((bucket) => (
        <Card key={bucket.label} className="shadow-sm">
          <CardContent className="p-3">
            <p className="text-[length:var(--text-xs)] font-medium text-foreground">{bucket.label}</p>
            <p className="mt-1 text-[length:var(--text-sm)] font-semibold text-primary">
              {formatPrice(bucket.min)} - {formatPrice(bucket.max)}
            </p>
            <p className="mt-0.5 text-[length:var(--text-xs)] text-muted-foreground">
              平均 {formatPrice(bucket.average)} · {bucket.count} 件
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function PriceDistributionChart({
  distribution,
}: {
  distribution: AnalysisData["distribution"];
}) {
  if (distribution.length === 0) {
    return null;
  }
  const max = Math.max(...distribution.map((item) => item.count), 1);
  return (
    <Card className="shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-[length:var(--text-sm)]">价格分布</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {distribution.map((bin) => (
          <div key={bin.range} className="flex items-center gap-2">
            <span className="w-12 shrink-0 text-[length:var(--text-xs)] text-muted-foreground">
              {bin.range}
            </span>
            <div className="min-w-0 flex-1">
              <Progress value={(bin.count / max) * 100} className="h-2" />
            </div>
            <span className="w-8 shrink-0 text-right text-[length:var(--text-xs)] text-muted-foreground">
              {bin.count}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function AnalysisSummary({ summary, recommendedRange }: Pick<AnalysisData, "summary" | "recommendedRange">) {
  return (
    <Card className="shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-[length:var(--text-sm)]">核心结论</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <ul className="list-disc space-y-1 pl-4 text-[length:var(--text-xs)] text-foreground/90">
          {summary.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {recommendedRange ? (
          <div className="mt-3 rounded-[var(--radius-md)] border border-border/60 bg-muted/20 p-3">
            <p className="text-[length:var(--text-xs)] text-muted-foreground">推荐购买区间</p>
            <p className="mt-1 text-[length:var(--text-sm)] font-semibold text-primary">
              {formatPrice(recommendedRange.min)} - {formatPrice(recommendedRange.max)}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function PurchaseRecommendation({
  product,
  analysis,
}: {
  product: Product | null;
  analysis: AnalysisData | null;
}) {
  const rec = analysis?.recommendation;
  if (!product || !rec) {
    return (
      <p className="py-8 text-center text-[length:var(--text-sm)] text-muted-foreground">
        分析完成后将生成购买建议
      </p>
    );
  }
  return (
    <Card className="shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-[length:var(--text-sm)]">推荐商品</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <p className="font-medium text-foreground">{product.title}</p>
          <p className="mt-1 text-xl font-semibold text-primary">{formatPrice(product.price)}</p>
          <p className="text-[length:var(--text-xs)] text-muted-foreground">
            {product.condition} · AI 推荐指数 {product.aiScore}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[length:var(--text-xs)] text-muted-foreground">
          <span>价格优势：{rec.priceAdvantage ?? "—"}</span>
          <span>成色：{rec.condition ?? "—"}</span>
          <span>卖家可信度：{rec.sellerTrust ?? "—"}</span>
          <span>风险：{rec.risk ?? "—"}</span>
        </div>
        <div>
          <p className="mb-1 text-[length:var(--text-xs)] font-medium text-foreground">推荐理由</p>
          <ul className="list-disc space-y-1 pl-4 text-[length:var(--text-xs)] text-muted-foreground">
            {rec.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

export function PriceTrend({ distribution }: { distribution: AnalysisData["distribution"] }) {
  if (distribution.length === 0) {
    return (
      <p className="py-8 text-center text-[length:var(--text-sm)] text-muted-foreground">
        暂无趋势数据
      </p>
    );
  }
  return (
    <Card className="shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-[length:var(--text-sm)]">价格趋势（模拟）</CardTitle>
      </CardHeader>
      <CardContent>
        <PriceDistributionChart distribution={distribution} />
        <p className="mt-3 text-[length:var(--text-xs)] text-muted-foreground">
          接入真实后端后，将展示平均价、最低价与商品数量随时间变化。
        </p>
      </CardContent>
    </Card>
  );
}
