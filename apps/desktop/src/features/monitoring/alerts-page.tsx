import { DataTable } from "@desk/ui";
import type { ColumnDef } from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { MonitoringShell } from "./monitoring-shell";

type Row = { title: string; kind: string; createdAt: string };

const COLUMNS: ColumnDef<Row, unknown>[] = [
  { accessorKey: "title", header: "提醒" },
  { accessorKey: "kind", header: "类型" },
  { accessorKey: "createdAt", header: "时间" },
];

export function MonitoringAlertsPage() {
  return (
    <MonitoringShell title="监控提醒" subtitle="利润率 / 价格 / 竞争变化告警（骨架）">
      <DataTable<Row> columns={COLUMNS} data={[]} emptyText="暂无提醒（骨架）" />
      <SectionEmpty title="功能骨架" description="后续支持已读与跳转商品。" />
    </MonitoringShell>
  );
}
