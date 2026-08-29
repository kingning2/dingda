import { BusinessTablePage } from "@/components/business/business-table-page";
import { MOCK_OPPORTUNITIES, OPPORTUNITY_COLUMNS } from "@/content/business";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/discovery/blue-ocean");

export default function DiscoveryBlueOceanPage() {
  return (
    <BusinessTablePage
      title="蓝海机会"
      subtitle="需求存在 + 竞争相对较低 + 利润合理"
      columns={[...OPPORTUNITY_COLUMNS]}
      rows={MOCK_OPPORTUNITIES.filter((row) => row.competition === "低")}
      discoveryTab="/console/discovery/blue-ocean"
      note="演示数据。"
    />
  );
}
