"use client";

import Link from "next/link";
import { useState } from "react";
import { buttonStyles } from "@/components/tailgrids/core/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/tailgrids/core/card";
import { DiscoveryTabs, PageHeader, SkeletonNote } from "@/components/business/shell";

const SCENARIOS = [
  {
    id: "a",
    title: "知道商品",
    placeholder: "例如：桌面风扇",
    hint: "Agent 将按关键词采集 1688 与闲鱼，并做同款利润分析。",
  },
  {
    id: "b",
    title: "知道品类",
    placeholder: "例如：宠物用品",
    hint: "从品类扩展候选商品后再双边分析。",
  },
  {
    id: "c",
    title: "完全不知道卖什么",
    placeholder: "例如：适合闲鱼新手的商品",
    hint: "按利润、竞争、门槛等约束生成候选机会。",
  },
] as const;

export default function DiscoveryStartPage() {
  const [scenario, setScenario] = useState<(typeof SCENARIOS)[number]["id"]>("c");
  const active = SCENARIOS.find((item) => item.id === scenario) ?? SCENARIOS[2];

  return (
    <div className="mt-6 space-y-5">
      <PageHeader
        title="开始选品"
        subtitle="发起 Agent 比价探索任务。连接闲鱼与 1688 账号后，桌面端将执行真实采集。"
      />
      <div className="space-y-4 px-2 lg:px-5">
        <DiscoveryTabs activePath="/console/discovery/start" />
        <SkeletonNote>
          演示骨架：提交后将在任务中心创建 Agent 探索任务。桌面端完成后，此处对接真实 IPC。
        </SkeletonNote>

        <div className="grid gap-3 sm:grid-cols-3">
          {SCENARIOS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setScenario(item.id)}
              className={buttonStyles({
                variant: scenario === item.id ? "primary" : "ghost",
                appearance: scenario === item.id ? "fill" : "outline",
                className: "h-auto flex-col items-start gap-1 px-4 py-3 text-left",
              })}
            >
              <span className="font-medium">{item.title}</span>
              <span className="text-xs font-normal opacity-80">{item.hint}</span>
            </button>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{active.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <input
              className="w-full rounded-lg border border-card-border bg-card-surface-area px-3 py-2 text-sm"
              placeholder={active.placeholder}
              defaultValue=""
            />
            <div className="flex flex-wrap gap-3">
              <button type="button" className={buttonStyles({ className: "bg-brand-500" })}>
                发起 Agent 探索（演示）
              </button>
              <Link href="/console/tasks" className={buttonStyles({ appearance: "outline" })}>
                查看任务中心
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
