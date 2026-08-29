import { DataTable } from "@desk/ui";
import type { ColumnDef } from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { MonitoringShell } from "./monitoring-shell";

type Row = { product: string; status: string; updatedAt: string };

const COLUMNS: ColumnDef<Row, unknown>[] = [
  { accessorKey: "product", header: "商品" },
  { accessorKey: "status", header: "状态" },
  { accessorKey: "updatedAt", header: "更新时间" },
];

export function MonitoringSubscriptionsPage() {
  return (
    <MonitoringShell title="监控列表" subtitle="已订阅监控的商品（骨架）">
      <DataTable<Row> columns={COLUMNS} data={[]} emptyText="暂无监控（骨架）" />
      <SectionEmpty title="功能骨架" description="接通后可启停监控并进入商品详情。" />
    </MonitoringShell>
  );
}
