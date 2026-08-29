import { MonitoringSkeletonPage } from "@/components/business/monitoring-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/monitoring/alerts");

export default function MonitoringAlertsPage() {
  return (
    <MonitoringSkeletonPage
      title="告警记录"
      subtitle="价格、竞品、利润触发的历史告警。"
      activePath="/console/monitoring/alerts"
      cardTitle="暂无告警"
      cardBody="对齐桌面端 monitoring/alerts。"
    />
  );
}
