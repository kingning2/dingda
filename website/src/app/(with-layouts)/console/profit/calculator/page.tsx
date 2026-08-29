import { SimpleSkeletonPage } from "@/components/business/simple-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/profit/calculator");

export default function ProfitCalculatorPage() {
  return (
    <SimpleSkeletonPage
      title="利润计算器"
      subtitle="输入 1688 采购价、闲鱼售价与成本项，测算利润空间。"
      cardTitle="计算器表单（骨架）"
      cardBody="对齐桌面端 profit/calculator。后续接入成本模板与默认费率。"
      note="演示骨架。桌面端完成后替换为真实表单与计算逻辑。"
    />
  );
}
