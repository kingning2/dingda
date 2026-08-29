import { BusinessTablePage } from "@/components/business/business-table-page";
import { MOCK_OPPORTUNITIES, OPPORTUNITY_COLUMNS } from "@/content/business";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/discovery/new");

export default function DiscoveryNewPage() {
  return (
    <BusinessTablePage
      title="新发现"
      subtitle="最近 Agent 探索采集、尚未充分分析的商品"
      columns={[...OPPORTUNITY_COLUMNS]}
      rows={MOCK_OPPORTUNITIES.slice(0, 2)}
      discoveryTab="/console/discovery/new"
      note="演示数据。"
    />
  );
}
