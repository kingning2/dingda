/**
 * 商品详情壳 + 子 Tab 占位。
 */

import { useMemo } from "react";
import { useLocation, useParams } from "react-router";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  PageGlowCard,
  PageScaffold,
} from "@desk/ui";
import { SectionEmpty, SubNavTabs } from "@components/product-shell";

function productTabs(productId: string) {
  const base = `/products/${productId}`;
  return [
    { path: base, label: "总览" },
    { path: `${base}/supply`, label: "供应端" },
    { path: `${base}/demand`, label: "销售端" },
    { path: `${base}/matches`, label: "同款" },
    { path: `${base}/profit`, label: "利润" },
    { path: `${base}/history`, label: "历史" },
  ];
}

function sectionFromPath(pathname: string, productId: string): string {
  const base = `/products/${productId}`;
  if (pathname.endsWith("/supply")) return "supply";
  if (pathname.endsWith("/demand")) return "demand";
  if (pathname.endsWith("/matches")) return "matches";
  if (pathname.endsWith("/profit")) return "profit";
  if (pathname.endsWith("/history")) return "history";
  if (pathname === base || pathname === `${base}/`) return "overview";
  return "overview";
}

const SECTION_COPY: Record<string, { title: string; description: string }> = {
  overview: {
    title: "为什么值得卖？",
    description: "推荐结论与 AI 分析摘要将展示于此（骨架）。",
  },
  supply: {
    title: "1688 供应端",
    description: "供应价区、供应商列表（骨架）。",
  },
  demand: {
    title: "闲鱼销售端",
    description: "售价区、Listing 数量与竞争（骨架）。",
  },
  matches: {
    title: "同款匹配",
    description: "匹配关系与置信度确认（骨架）。",
  },
  profit: {
    title: "商品利润",
    description: "成本拆解、利润率、ROI（骨架）。",
  },
  history: {
    title: "价格历史",
    description: "价/竞争时间序列（骨架）。",
  },
};

/** 商品详情：总览强调推荐结论，其余 Tab 空态。 */
export function ProductDetailPage() {
  const { productId = "demo" } = useParams();
  const { pathname } = useLocation();
  const tabs = useMemo(() => productTabs(productId), [productId]);
  const section = sectionFromPath(pathname, productId);
  const copy = SECTION_COPY[section] ?? SECTION_COPY.overview;
  const isOverview = section === "overview";

  return (
    <PageScaffold
      title="商品详情"
      subtitle={`商品 ${productId} — 这个商品为什么值得卖？`}
      ambient={isOverview ? "spotlight" : "none"}
      containerPadding="sm"
      toolbar={<SubNavTabs tabs={tabs} activePath={pathname} />}
    >
      {isOverview ? (
        <PageGlowCard>
          <div className="space-y-3 p-4">
            <p className="text-[length:var(--text-sm)] font-medium text-foreground">
              推荐结论（骨架）
            </p>
            <p className="text-[length:var(--text-sm)] text-muted-foreground">
              推荐卖 / 谨慎进入 / 不建议卖 — 原因将在业务接通后展示。
            </p>
          </div>
        </PageGlowCard>
      ) : null}

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>{copy.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <SectionEmpty title="功能骨架" description={copy.description} />
        </CardContent>
      </Card>
    </PageScaffold>
  );
}
