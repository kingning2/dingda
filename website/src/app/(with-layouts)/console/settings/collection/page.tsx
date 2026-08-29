import { SettingsSkeletonPage } from "@/components/business/simple-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/settings/collection");

export default function SettingsCollectionPage() {
  return (
    <SettingsSkeletonPage
      title="采集"
      subtitle="爬虫并发、重试、代理等采集参数。"
      activePath="/console/settings/collection"
      cardTitle="采集配置（骨架）"
      cardBody="对齐桌面端 settings/collection。"
    />
  );
}
