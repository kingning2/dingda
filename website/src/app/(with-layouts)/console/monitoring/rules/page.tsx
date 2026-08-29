import { MonitoringSkeletonPage } from "@/components/business/monitoring-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/monitoring/rules");

export default function MonitoringRulesPage() {
  return (
    <MonitoringSkeletonPage
      title="规则配置"
      subtitle="配置监控阈值：价格波动、利润率下降、竞品上架等。"
      activePath="/console/monitoring/rules"
      cardTitle="暂无规则"
      cardBody="对齐桌面端 monitoring/rules。"
    />
  );
}
