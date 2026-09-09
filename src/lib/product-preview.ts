/**
 * 会话商品预览：打开自绘 Modal（不嵌入外站）。
 */

import type { AccountPlatform } from "@/contracts/account";
import type { AgentWorkProductItem } from "@/contracts/ai-work";
import type { CrawlPlatform, CrawlProductItem } from "@/contracts/crawler";
import { getHostCapabilities } from "@/lib/capabilities";

export type ProductPreviewTarget = Pick<
  CrawlProductItem,
  | "id"
  | "title"
  | "price"
  | "platform"
  | "seller"
  | "location"
  | "image_url"
  | "product_url"
  | "want_count"
  | "browse_count"
> & {
  platform?: CrawlPlatform | AccountPlatform | string;
};

type PreviewListener = (target: ProductPreviewTarget | null) => void;

let previewListener: PreviewListener | null = null;

/** Layout 挂载 Dialog 后订阅；返回取消函数。 */
export function subscribeProductPreview(listener: PreviewListener): () => void {
  previewListener = listener;
  return () => {
    if (previewListener === listener) previewListener = null;
  };
}

function normalizeHttpUrl(url: string | null | undefined): string | null {
  const trimmed = (url || "").trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

/** 打开自绘商品详情 Modal。 */
export function openProductPreview(
  item: ProductPreviewTarget | AgentWorkProductItem,
): "dialog" | "none" {
  if (!item?.title?.trim() && !item?.id) return "none";
  if (!previewListener) {
    console.warn("product preview dialog not mounted");
    const url = normalizeHttpUrl(item.product_url);
    if (url && !getHostCapabilities().desktop) {
      openProductInBrowserTab(url);
    }
    return "none";
  }
  previewListener({
    id: item.id,
    title: item.title,
    price: item.price,
    platform: item.platform,
    seller: item.seller,
    location: item.location,
    image_url: item.image_url,
    product_url: normalizeHttpUrl(item.product_url) ?? item.product_url,
    want_count: item.want_count,
    browse_count: item.browse_count,
  });
  return "dialog";
}

export function closeProductPreviewUi(): void {
  previewListener?.(null);
}

export function openProductInBrowserTab(url: string): void {
  const normalized = normalizeHttpUrl(url);
  if (!normalized) return;
  window.open(normalized, "_blank", "noopener,noreferrer");
}
