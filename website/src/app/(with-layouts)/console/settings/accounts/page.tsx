import { SettingsSkeletonPage } from "@/components/business/simple-skeleton-page";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/settings/accounts");

export default function SettingsAccountsPage() {
  return (
    <SettingsSkeletonPage
      title="账号"
      subtitle="闲鱼、1688、小红书账号连接与 Cookie 管理。"
      activePath="/console/settings/accounts"
      cardTitle="账号 Hub（骨架）"
      cardBody="对齐桌面端 settings/accounts 与各平台 accounts 页。选品前需完成闲鱼 + 1688 双端连接。"
    />
  );
}
