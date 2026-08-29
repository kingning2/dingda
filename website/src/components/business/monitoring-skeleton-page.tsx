import { PlaceholderCard, MonitoringTabs, PageHeader, SkeletonNote } from "./shell";

export function MonitoringSkeletonPage({
  title,
  subtitle,
  activePath,
  cardTitle,
  cardBody,
}: {
  title: string;
  subtitle: string;
  activePath: string;
  cardTitle: string;
  cardBody: string;
}) {
  return (
    <div className="mt-6 space-y-5">
      <PageHeader title={title} subtitle={subtitle} />
      <div className="space-y-4 px-2 lg:px-5">
        <MonitoringTabs activePath={activePath} />
        <SkeletonNote>演示骨架，对齐桌面端 monitoring 模块。</SkeletonNote>
        <PlaceholderCard title={cardTitle} description={cardBody} />
      </div>
    </div>
  );
}
