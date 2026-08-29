import { Card, CardContent, CardHeader, CardTitle } from "@/components/tailgrids/core/card";
import { PageHeader, PlaceholderCard, SettingsTabs, SkeletonNote } from "./shell";

export function SimpleSkeletonPage({
  title,
  subtitle,
  cardTitle,
  cardBody,
  note,
}: {
  title: string;
  subtitle: string;
  cardTitle: string;
  cardBody: string;
  note?: string;
}) {
  return (
    <div className="mt-6 space-y-5">
      <PageHeader title={title} subtitle={subtitle} />
      <div className="space-y-4 px-2 lg:px-5">
        {note ? <SkeletonNote>{note}</SkeletonNote> : null}
        <Card>
          <CardHeader>
            <CardTitle>{cardTitle}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm leading-6 text-text-tertiary">{cardBody}</CardContent>
        </Card>
      </div>
    </div>
  );
}

export function SettingsSkeletonPage({
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
        <SettingsTabs activePath={activePath} />
        <SkeletonNote>设置页骨架，对齐桌面端 `/settings/*` 路由。</SkeletonNote>
        <PlaceholderCard title={cardTitle} description={cardBody} />
      </div>
    </div>
  );
}
