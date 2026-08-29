import { BusinessTablePage } from "@/components/business/business-table-page";
import { MOCK_OPPORTUNITIES, OPPORTUNITY_COLUMNS } from "@/content/business";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/discovery/high-profit");

export default function DiscoveryHighProfitPage() {
  return (
    <BusinessTablePage
      title="高利润机会"
      subtitle="按采购价、闲鱼售价、利润、利润率、竞争度筛选"
      columns={[...OPPORTUNITY_COLUMNS]}
      rows={MOCK_OPPORTUNITIES}
      discoveryTab="/console/discovery/high-profit"
      note="演示数据。桌面端完成后对接选品发现 API。"
    />
  );
}
