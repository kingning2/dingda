import { BusinessTablePage } from "@/components/business/business-table-page";
import { MOCK_TASKS, TASK_COLUMNS } from "@/content/business";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/tasks");

export default function TasksPage() {
  return (
    <BusinessTablePage
      title="任务中心"
      subtitle="Agent 比价探索、热门扫描等任务（投影 AgentRun）"
      columns={[...TASK_COLUMNS]}
      rows={MOCK_TASKS}
      note="演示数据。对接 `agentRunList` / `agentRunStart` IPC。"
    />
  );
}
