/**
 * 工作台占位 — Bento 七区块，决策导向，无经营 KPI。
 */

import { Button, BentoCard, BentoGrid, PageScaffold } from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { useWorkspaceNav } from "../../app/use-workspace-tabs";

const SECTIONS = [
  { title: "今日商品机会", description: "今天最值得关注的选品机会（骨架）。" },
  { title: "高利润商品", description: "按利润与利润率排序的机会（骨架）。" },
  { title: "新发现商品", description: "最近采集、尚未充分分析（骨架）。" },
  { title: "利润率上升", description: "利润变好的商品（骨架）。" },
  { title: "竞争下降", description: "竞争变弱的商品（骨架）。" },
  { title: "监控提醒", description: "价/竞/利告警（骨架）。" },
  { title: "最近任务", description: "最近选品与采集任务（骨架）。" },
] as const;

/** 工作台：今天有什么值得卖？ */
export function DashboardPage() {
  const { selectTab } = useWorkspaceNav();

  return (
    <PageScaffold
      title="工作台"
      subtitle="今天有什么值得卖？"
      ambient="spotlight"
      containerPadding="md"
      extra={
        <Button type="button" size="sm" onClick={() => selectTab("/discovery/start")}>
          开始选品
        </Button>
      }
    >
      <BentoGrid columns={3}>
        {SECTIONS.map((section, index) => (
          <BentoCard
            key={section.title}
            colSpan={index === 0 ? 2 : 1}
            rowSpan={index === 0 ? 2 : 1}
            glow={index === 0}
          >
            <div className="flex h-full flex-col gap-2 p-4">
              <h2 className="text-[length:var(--text-sm)] font-medium text-foreground">
                {section.title}
              </h2>
              <SectionEmpty title="暂无数据" description={section.description} />
            </div>
          </BentoCard>
        ))}
      </BentoGrid>
    </PageScaffold>
  );
}
