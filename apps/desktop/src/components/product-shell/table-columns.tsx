/**
 * 选品相关 DataTable 列定义（骨架无数据）。
 */

import type { ColumnDef } from "@desk/ui";

export type OpportunityRow = {
  title: string;
  supplyPrice: string;
  demandPrice: string;
  profit: string;
  margin: string;
  competition: string;
  score: string;
};

export type ProductRow = {
  title: string;
  category: string;
  supplyMin: string;
  supplierCount: string;
  demandPrice: string;
  listingCount: string;
  profit: string;
  margin: string;
  competition: string;
  score: string;
  updatedAt: string;
};

export type TaskRow = {
  id: string;
  type: string;
  status: string;
  progress: string;
  updatedAt: string;
};

/** 机会列表列。 */
export const OPPORTUNITY_TABLE_COLUMNS: ColumnDef<OpportunityRow, unknown>[] = [
  { accessorKey: "title", header: "商品" },
  { accessorKey: "supplyPrice", header: "1688采购价" },
  { accessorKey: "demandPrice", header: "闲鱼售价" },
  { accessorKey: "profit", header: "预计利润" },
  { accessorKey: "margin", header: "利润率" },
  { accessorKey: "competition", header: "竞争度" },
  { accessorKey: "score", header: "机会评分" },
];

/** 商品库列。 */
export const PRODUCT_TABLE_COLUMNS: ColumnDef<ProductRow, unknown>[] = [
  { accessorKey: "title", header: "商品" },
  { accessorKey: "category", header: "类目" },
  { accessorKey: "supplyMin", header: "1688最低价" },
  { accessorKey: "supplierCount", header: "1688供应商数" },
  { accessorKey: "demandPrice", header: "闲鱼市场价" },
  { accessorKey: "listingCount", header: "闲鱼商品数" },
  { accessorKey: "profit", header: "预计利润" },
  { accessorKey: "margin", header: "利润率" },
  { accessorKey: "competition", header: "竞争度" },
  { accessorKey: "score", header: "机会评分" },
  { accessorKey: "updatedAt", header: "更新时间" },
];

/** 任务列表列。 */
export const TASK_TABLE_COLUMNS: ColumnDef<TaskRow, unknown>[] = [
  { accessorKey: "type", header: "类型" },
  { accessorKey: "status", header: "状态" },
  { accessorKey: "progress", header: "进度" },
  { accessorKey: "updatedAt", header: "更新时间" },
];
