import { BusinessTablePage } from "@/components/business/business-table-page";
import { MOCK_OPPORTUNITIES, OPPORTUNITY_COLUMNS } from "@/content/business";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/discovery/hot");

export default function DiscoveryHotPage() {
  return (
    <BusinessTablePage
      title="热门机会"
      subtitle="按市场活跃度与近期热度筛选"
      columns={[...OPPORTUNITY_COLUMNS]}
      rows={MOCK_OPPORTUNITIES}
      discoveryTab="/console/discovery/hot"
      note="演示数据。对接后将展示 Agent 探索到的近期热门品类。"
    />
  );
}
