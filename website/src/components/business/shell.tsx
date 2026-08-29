import { Card, CardContent, CardHeader, CardTitle } from "@/components/tailgrids/core/card";
import { cn } from "@/utils/cn";
import Link from "next/link";

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 px-2 sm:flex-row sm:items-start sm:justify-between lg:px-6">
      <div>
        <h1 className="mb-1 text-[28px] leading-8 font-medium text-text-primary">{title}</h1>
        <p className="text-sm leading-5 text-text-tertiary">{subtitle}</p>
      </div>
      {action}
    </div>
  );
}

export function PlaceholderCard({
  title,
  description,
  className,
}: {
  title: string;
  description: string;
  className?: string;
}) {
  return (
    <Card className={cn("h-full", className)}>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex min-h-24 flex-col items-center justify-center rounded-lg border border-dashed border-card-border bg-background-gray-primary px-4 py-8 text-center">
          <p className="text-sm font-medium text-text-secondary">暂无数据</p>
          <p className="mt-1 max-w-xs text-xs leading-5 text-text-tertiary">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export function SkeletonNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-lg border border-card-border bg-background-gray-primary px-4 py-3 text-xs leading-5 text-text-tertiary">
      {children}
    </p>
  );
}

export function SettingsTabs({ activePath }: { activePath: string }) {
  const tabs = [
    { path: "/console/settings/general", label: "通用" },
    { path: "/console/settings/accounts", label: "账号" },
    { path: "/console/settings/collection", label: "采集" },
    { path: "/console/settings/profit", label: "利润默认" },
    { path: "/console/settings/ai", label: "AI 模型" },
  ];

  return (
    <nav className="flex flex-wrap gap-2 border-b border-card-border pb-3">
      {tabs.map((tab) => (
        <Link
          key={tab.path}
          href={tab.path}
          className={cn(
            "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            activePath === tab.path || activePath.startsWith(`${tab.path}/`)
              ? "bg-brand-500 text-white"
              : "text-text-secondary hover:bg-background-gray-primary hover:text-text-primary",
          )}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}

export function MonitoringTabs({ activePath }: { activePath: string }) {
  const tabs = [
    { path: "/console/monitoring/subscriptions", label: "监控订阅" },
    { path: "/console/monitoring/alerts", label: "告警记录" },
    { path: "/console/monitoring/rules", label: "规则配置" },
  ];

  return (
    <nav className="flex flex-wrap gap-2">
      {tabs.map((tab) => (
        <Link
          key={tab.path}
          href={tab.path}
          className={cn(
            "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            activePath === tab.path
              ? "bg-brand-500 text-white"
              : "text-text-secondary hover:bg-background-gray-primary hover:text-text-primary",
          )}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}

export function DiscoveryTabs({ activePath }: { activePath: string }) {
  const tabs = [
    { path: "/console/discovery/high-profit", label: "高利润" },
    { path: "/console/discovery/hot", label: "热门" },
    { path: "/console/discovery/blue-ocean", label: "蓝海" },
    { path: "/console/discovery/new", label: "新发现" },
    { path: "/console/discovery/start", label: "开始选品" },
  ];

  return (
    <nav className="flex flex-wrap gap-2">
      {tabs.map((tab) => (
        <Link
          key={tab.path}
          href={tab.path}
          className={cn(
            "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            activePath === tab.path
              ? "bg-brand-500 text-white"
              : "text-text-secondary hover:bg-background-gray-primary hover:text-text-primary",
          )}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
