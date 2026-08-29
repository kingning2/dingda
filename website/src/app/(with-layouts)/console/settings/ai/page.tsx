import { SettingsSkeletonPage } from "@/components/business/simple-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/settings/ai");

export default function SettingsAiPage() {
  return (
    <SettingsSkeletonPage
      title="AI 模型"
      subtitle="Agent 比价探索使用的模型与 API 配置。"
      activePath="/console/settings/ai"
      cardTitle="AI 配置（骨架）"
      cardBody="对齐桌面端 settings/ai。Agent 负责规划关键词、分析利润，不自动替你上架或发消息。"
    />
  );
}
