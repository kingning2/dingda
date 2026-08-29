import { SettingsSkeletonPage } from "@/components/business/simple-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/settings/profit");

export default function SettingsProfitPage() {
  return (
    <SettingsSkeletonPage
      title="利润默认"
      subtitle="默认运费、扣点、包装费等利润测算基线。"
      activePath="/console/settings/profit"
      cardTitle="利润默认值（骨架）"
      cardBody="对齐桌面端 settings/profit。"
    />
  );
}
