/**
 * 会话商品预览：用已抓取字段自绘 Modal，不嵌入外站 Webview / iframe。
 */

import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  openProductInBrowserTab,
  subscribeProductPreview,
  type ProductPreviewTarget,
} from "@/lib/product-preview";

const PLATFORM_LABEL: Record<string, string> = {
  xianyu: "闲鱼",
  xiaohongshu: "小红书",
  ali1688: "1688",
};

/** 挂在 AI 工作 Layout：订阅 openProductPreview。 */
export function ProductPreviewHost() {
  const [item, setItem] = useState<ProductPreviewTarget | null>(null);

  useEffect(() => subscribeProductPreview(setItem), []);

  return (
    <ProductPreviewDialog
      open={Boolean(item)}
      item={item}
      onOpenChange={(open) => {
        if (!open) setItem(null);
      }}
    />
  );
}

export type ProductPreviewDialogProps = {
  open: boolean;
  item: ProductPreviewTarget | null;
  onOpenChange: (open: boolean) => void;
};

export function ProductPreviewDialog({ open, item, onOpenChange }: ProductPreviewDialogProps) {
  const title = (item?.title || "").trim() || "商品详情";
  const url = item?.product_url?.trim() || "";
  const platform = item?.platform ? PLATFORM_LABEL[item.platform] || item.platform : null;
  const meta = [
    platform,
    item?.seller ? `卖家 ${item.seller}` : null,
    item?.location || null,
    item?.want_count ? `想要 ${item.want_count}` : null,
    item?.browse_count ? `浏览/赞 ${item.browse_count}` : null,
  ].filter(Boolean);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(88vh,720px)] w-[min(100%-1.5rem,420px)] max-w-none flex-col gap-0 overflow-hidden p-0 sm:max-w-none">
        <DialogHeader className="shrink-0 gap-1 border-b border-border/70 px-4 py-3 pr-12 text-left">
          <DialogTitle className="line-clamp-2 text-sm">{title}</DialogTitle>
          {meta.length > 0 ? (
            <DialogDescription className="truncate text-xs">{meta.join(" · ")}</DialogDescription>
          ) : null}
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {!item ? (
            <p className="text-sm text-muted-foreground">没有可展示的商品</p>
          ) : (
            <div className="space-y-4">
              <div className="overflow-hidden rounded-lg bg-muted/40">
                <Avatar className="aspect-[4/3] h-auto w-full rounded-none after:rounded-none">
                  {item.image_url ? (
                    <AvatarImage
                      src={item.image_url}
                      alt=""
                      className="size-full rounded-none object-contain"
                    />
                  ) : null}
                  <AvatarFallback className="size-full rounded-none text-sm">暂无封面</AvatarFallback>
                </Avatar>
              </div>

              <div className="space-y-2">
                <p className="text-2xl font-semibold tracking-tight text-foreground">
                  {item.price?.trim() || "—"}
                </p>
                <h3 className="text-sm leading-snug font-medium text-foreground">{item.title}</h3>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {platform ? <Badge variant="secondary">{platform}</Badge> : null}
                  {item.id ? (
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {item.id}
                    </Badge>
                  ) : null}
                </div>
              </div>

              <dl className="space-y-2 text-sm">
                {item.seller ? (
                  <div className="flex justify-between gap-3">
                    <dt className="shrink-0 text-muted-foreground">卖家</dt>
                    <dd className="truncate text-right">{item.seller}</dd>
                  </div>
                ) : null}
                {item.location ? (
                  <div className="flex justify-between gap-3">
                    <dt className="shrink-0 text-muted-foreground">地区</dt>
                    <dd className="truncate text-right">{item.location}</dd>
                  </div>
                ) : null}
                {item.want_count ? (
                  <div className="flex justify-between gap-3">
                    <dt className="shrink-0 text-muted-foreground">想要</dt>
                    <dd className="text-right">{item.want_count}</dd>
                  </div>
                ) : null}
                {item.browse_count ? (
                  <div className="flex justify-between gap-3">
                    <dt className="shrink-0 text-muted-foreground">浏览/赞</dt>
                    <dd className="text-right">{item.browse_count}</dd>
                  </div>
                ) : null}
                {url ? (
                  <div className="flex justify-between gap-3">
                    <dt className="shrink-0 text-muted-foreground">链接</dt>
                    <dd className="truncate text-right font-mono text-[11px] text-muted-foreground">
                      {url}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border/70 px-4 py-3">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!url}
            onClick={() => {
              if (url) openProductInBrowserTab(url);
            }}
          >
            <ExternalLink className="size-3.5" />
            浏览器打开
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
