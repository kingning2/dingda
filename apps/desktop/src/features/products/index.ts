/**
 * 商品库 Feature。
 */

import { Package } from "@desk/ui/icons";

export { ProductsPage } from "./products-page";
export { ProductDetailPage } from "./product-detail-page";

export const PRODUCTS_PATH = "/products" as const;

export const productsFeature = {
  id: "products",
  path: PRODUCTS_PATH,
  navItem: {
    id: "products",
    path: PRODUCTS_PATH,
    label: "商品库",
    icon: Package,
  },
};
