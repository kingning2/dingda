import { BusinessTablePage } from "@/components/business/business-table-page";
import { MOCK_PRODUCTS, PRODUCT_COLUMNS } from "@/content/business";
import { demoPageMetadata } from "@/lib/seo/demo-meta";
import type { Metadata } from "next";

export const metadata: Metadata = demoPageMetadata("/console/products");

export default function ProductsPage() {
  return (
    <BusinessTablePage
      title="商品库"
      subtitle="标准商品目录（非爬虫原始堆、非卖家自有闲鱼 Listing）"
      columns={[...PRODUCT_COLUMNS]}
      rows={MOCK_PRODUCTS}
      note="演示数据。对接桌面端 Canonical Product 列表。"
    />
  );
}
