/**
 * 商品库列表占位。
 */

import { DataTable, PageScaffold } from "@desk/ui";
import {
  PRODUCT_TABLE_COLUMNS,
  SectionEmpty,
  type ProductRow,
} from "@components/product-shell";

/** Canonical 商品目录骨架。 */
export function ProductsPage() {
  return (
    <PageScaffold
      title="商品库"
      subtitle="标准商品目录（非爬虫原始堆、非卖家自有闲鱼 Listing）"
      ambient="none"
      containerPadding="sm"
    >
      <DataTable<ProductRow>
        columns={PRODUCT_TABLE_COLUMNS}
        data={[]}
        emptyText="暂无商品（骨架）"
      />
      <SectionEmpty
        title="功能骨架"
        description="后续接入 Canonical Product / Listing / 机会评分。"
      />
    </PageScaffold>
  );
}
