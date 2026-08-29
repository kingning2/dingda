/**
 * 成本模板列表占位。
 */

import { DataTable, PageScaffold } from "@desk/ui";
import type { ColumnDef } from "@desk/ui";
import { SectionEmpty, SubNavTabs } from "@components/product-shell";
import { useLocation } from "react-router";

const PROFIT_TABS = [
  { path: "/profit/calculator", label: "计算器" },
  { path: "/profit/templates", label: "成本模板" },
];

type TemplateRow = { name: string; updatedAt: string };

const COLUMNS: ColumnDef<TemplateRow, unknown>[] = [
  { accessorKey: "name", header: "模板名称" },
  { accessorKey: "updatedAt", header: "更新时间" },
];

/** 成本模板骨架。 */
export function ProfitTemplatesPage() {
  const { pathname } = useLocation();

  return (
    <PageScaffold
      title="成本模板"
      subtitle="管理多套成本假设（骨架）"
      ambient="none"
      containerPadding="sm"
      toolbar={<SubNavTabs tabs={PROFIT_TABS} activePath={pathname} />}
    >
      <DataTable<TemplateRow> columns={COLUMNS} data={[]} emptyText="暂无模板（骨架）" />
      <SectionEmpty title="功能骨架" description="后续可设置默认模板并同步到设置页。" />
    </PageScaffold>
  );
}
