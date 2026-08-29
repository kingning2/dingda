import { SimpleSkeletonPage } from "@/components/business/simple-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/profit/templates");

export default function ProfitTemplatesPage() {
  return (
    <SimpleSkeletonPage
      title="成本模板"
      subtitle="运费、包装、平台扣点等成本项模板，供利润计算复用。"
      cardTitle="模板列表（骨架）"
      cardBody="对齐桌面端 profit/templates。"
      note="演示骨架。桌面端完成后对接模板 CRUD。"
    />
  );
}
