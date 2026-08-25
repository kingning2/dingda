/**
 * Feature 占位页。
 *
 * @author coisini
 * @created 2026-07-20
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle, PageScaffold } from "@desk/ui";

/**
 * 占位页属性。
 *
 * @author coisini
 * @created 2026-07-20
 */
export interface FeaturePlaceholderPageProps {
  /** 标题。 */
  title: string;
  /** 描述。 */
  description?: string;
}

/**
 * 开发中 Feature 的占位展示。
 *
 * @author coisini
 * @created 2026-07-20
 *
 * @param props - 见 {@link FeaturePlaceholderPageProps}
 * @returns 占位页节点
 */
export function FeaturePlaceholderPage({ title, description }: FeaturePlaceholderPageProps) {
  return (
    <PageScaffold subtitle={description ?? `${title} — 即将推出`}>
      <Card variant="glass" className="w-full">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </CardHeader>
        <CardContent>
          <p className="text-[length:var(--text-sm)] text-muted-foreground">
            该功能即将推出，敬请期待。
          </p>
        </CardContent>
      </Card>
    </PageScaffold>
  );
}
