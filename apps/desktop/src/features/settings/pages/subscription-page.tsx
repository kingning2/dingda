import { Button, Card, CardContent, CardHeader, CardTitle } from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { SettingsLayoutPage } from "../settings-layout";

export function SettingsSubscriptionPage() {
  return (
    <SettingsLayoutPage>
      <div className="mx-auto flex w-full max-w-lg flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>当前套餐：Free</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-[length:var(--text-sm)] text-muted-foreground">
            <p>剩余额度、到期时间将在此展示。</p>
            <Button type="button" size="sm" disabled>
              升级 Pro（骨架）
            </Button>
          </CardContent>
        </Card>
        <SectionEmpty
          title="Pro 价值"
          description="更多商品分析、历史价格、自动监控、AI 深度分析 — 不按爬取次数收费。"
        />
      </div>
    </SettingsLayoutPage>
  );
}
