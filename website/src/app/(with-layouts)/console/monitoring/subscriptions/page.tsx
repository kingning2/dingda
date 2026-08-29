import { MonitoringSkeletonPage } from "@/components/business/monitoring-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/monitoring/subscriptions");

export default function MonitoringSubscriptionsPage() {
  return (
    <MonitoringSkeletonPage
      title="监控订阅"
      subtitle="为商品库条目订阅价格、竞品与利润变动提醒。"
      activePath="/console/monitoring/subscriptions"
      cardTitle="暂无订阅"
      cardBody="对齐桌面端 monitoring/subscriptions。"
    />
  );
}
