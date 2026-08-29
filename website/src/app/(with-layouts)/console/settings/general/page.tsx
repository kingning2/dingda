import { SettingsSkeletonPage } from "@/components/business/simple-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/settings/general");

export default function SettingsGeneralPage() {
  return (
    <SettingsSkeletonPage
      title="通用"
      subtitle="语言、主题、启动项等基础偏好。"
      activePath="/console/settings/general"
      cardTitle="通用设置（骨架）"
      cardBody="对齐桌面端 settings/general。"
    />
  );
}
