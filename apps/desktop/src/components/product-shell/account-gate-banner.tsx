/**
 * 双端登录门禁提示条（骨架：UI 提示，不做后端硬拦）。
 */

import { Button, Card, CardContent } from "@desk/ui";
import { useWorkspaceNav } from "../../app/use-workspace-tabs";

export interface AccountGateBannerProps {
  /** 闲鱼是否已连接；骨架可传 false。 */
  xianyuConnected?: boolean;
  /** 1688 是否已连接；骨架可传 false。 */
  ali1688Connected?: boolean;
}

/**
 * 展示闲鱼 / 1688 连接状态与采集是否解锁；引导去设置账号。
 */
export function AccountGateBanner({
  xianyuConnected = false,
  ali1688Connected = false,
}: AccountGateBannerProps) {
  const { selectTab } = useWorkspaceNav();
  const canCrawl = xianyuConnected && ali1688Connected;
  const missing: string[] = [];
  if (!xianyuConnected) {
    missing.push("闲鱼");
  }
  if (!ali1688Connected) {
    missing.push("1688");
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-[length:var(--text-sm)] font-medium text-foreground">
            采集状态：{canCrawl ? "已解锁" : "未解锁"}
          </p>
          <p className="text-[length:var(--text-xs)] text-muted-foreground">
            闲鱼 {xianyuConnected ? "已连接" : "未连接"} · 1688{" "}
            {ali1688Connected ? "已连接" : "未连接"}
            {missing.length > 0
              ? ` — 请先扫码登录：${missing.join("、")}`
              : " — 两端已登录，可开始选品采集"}
          </p>
        </div>
        <Button type="button" size="sm" onClick={() => selectTab("/settings/accounts")}>
          去连接账号
        </Button>
      </CardContent>
    </Card>
  );
}
