/**
 * 开始选品 — 场景 A/B/C 表单壳 + 双端门禁提示。
 */

import { useState } from "react";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Form,
  FormInput,
  z,
} from "@desk/ui";
import { useAccountGateStatus } from "@components/accounts";
import { AccountGateBanner, SectionEmpty } from "@components/product-shell";
import { DiscoveryShell } from "../discovery-shell";

const startSchema = z.object({
  query: z.string().min(1, "请输入内容"),
});

type Scenario = "a" | "b" | "c";

const SCENARIO_COPY: Record<
  Scenario,
  { title: string; placeholder: string; hint: string }
> = {
  a: {
    title: "知道商品",
    placeholder: "例如：桌面风扇",
    hint: "将按关键词采集 1688 与闲鱼并做同款利润分析。",
  },
  b: {
    title: "知道品类",
    placeholder: "例如：宠物用品",
    hint: "将从品类扩展候选商品后再双边分析。",
  },
  c: {
    title: "完全不知道卖什么",
    placeholder: "例如：适合闲鱼新手的商品",
    hint: "将按利润、竞争、门槛等约束生成候选机会。",
  },
};

/** 开始选品页（双端登录门禁接通后允许提交）。 */
export function DiscoveryStartPage() {
  const [scenario, setScenario] = useState<Scenario>("c");
  const { xianyuConnected, ali1688Connected, canCrawl } = useAccountGateStatus();
  const copy = SCENARIO_COPY[scenario];

  return (
    <DiscoveryShell
      title="开始选品"
      subtitle="选择场景并发起选品任务"
    >
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
        <AccountGateBanner
          xianyuConnected={xianyuConnected}
          ali1688Connected={ali1688Connected}
        />

        <div className="flex flex-wrap gap-1">
          {(Object.keys(SCENARIO_COPY) as Scenario[]).map((key) => (
            <Button
              key={key}
              type="button"
              size="sm"
              variant={scenario === key ? "secondary" : "ghost"}
              onClick={() => setScenario(key)}
            >
              场景 {key.toUpperCase()}：{SCENARIO_COPY[key].title}
            </Button>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{copy.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-[length:var(--text-sm)] text-muted-foreground">{copy.hint}</p>
            <Form
              schema={startSchema}
              defaultValues={{ query: "" }}
              onSubmit={() => {
                /* 骨架：不发起任务 */
              }}
            >
              <FormInput name="query" label="输入" placeholder={copy.placeholder} />
              <div className="pt-2">
                <Button type="submit" size="sm" disabled={!canCrawl}>
                  开始选品
                </Button>
              </div>
            </Form>
            {!canCrawl ? (
              <SectionEmpty
                title="请先完成双端扫码登录"
                description="闲鱼与 1688 都登录后才能采集。点击上方「去连接账号」。"
              />
            ) : null}
          </CardContent>
        </Card>
      </div>
    </DiscoveryShell>
  );
}
