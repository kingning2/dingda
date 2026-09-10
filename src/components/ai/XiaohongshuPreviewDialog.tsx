/**
 * 小红书笔记预览：封面 + 正文/OCR + 评论；与闲鱼商品卡分开。
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
import { fetchCrawlerProduct } from "@/lib/crawler-api";
import {
  openProductInBrowserTab,
  type ProductPreviewTarget,
} from "@/lib/product-preview";

export type XiaohongshuPreviewDialogProps = {
  open: boolean;
  item: ProductPreviewTarget | null;
  onOpenChange: (open: boolean) => void;
};

export function XiaohongshuPreviewDialog({
  open,
  item,
  onOpenChange,
}: XiaohongshuPreviewDialogProps) {
  const [detail, setDetail] = useState<ProductPreviewTarget | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !item?.id) {
      setDetail(null);
      setLoadingDetail(false);
      setDetailError(null);
      return;
    }

    const isVideo = (item.note_type || "").toLowerCase() === "video";
    const hasDetail =
      Boolean(item.content_text?.trim() || item.desc?.trim() || item.ocr_text?.trim()) ||
      (Array.isArray(item.comments) && item.comments.length > 0);
    if (isVideo || hasDetail) {
      setDetail(item);
      setLoadingDetail(false);
      setDetailError(null);
      return;
    }

    const ac = new AbortController();
    setDetail(item);
    setLoadingDetail(true);
    setDetailError(null);

    void fetchCrawlerProduct(
      {
        platform: "xiaohongshu",
        item_id: item.id,
        xsec_token: item.xsec_token ?? null,
      },
      { signal: ac.signal },
    )
      .then((res) => {
        if (ac.signal.aborted) return;
        if (!res.ok || !res.item) {
          setDetailError(res.message?.trim() || "笔记详情加载失败");
          return;
        }
        const next = res.item;
        setDetail({
          ...item,
          title: next.title || item.title,
          seller: next.seller ?? item.seller,
          image_url: next.image_url ?? item.image_url,
          product_url: next.product_url ?? item.product_url,
          want_count: next.want_count ?? item.want_count,
          browse_count: next.browse_count ?? item.browse_count,
          desc: next.desc ?? item.desc,
          comments: next.comments ?? item.comments ?? [],
          ocr_text: next.ocr_text ?? item.ocr_text,
          content_text: next.content_text ?? item.content_text,
          note_type: next.note_type ?? item.note_type,
          xsec_token: next.xsec_token ?? item.xsec_token,
        });
      })
      .catch((err: unknown) => {
        if (ac.signal.aborted) return;
        setDetailError(err instanceof Error ? err.message : "笔记详情加载失败");
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoadingDetail(false);
      });

    return () => ac.abort();
  }, [open, item]);

  const view = detail ?? item;
  const title = (view?.title || "").trim() || "笔记详情";
  const url = view?.product_url?.trim() || "";
  const isVideo = (view?.note_type || "").toLowerCase() === "video";
  const body =
    (view?.content_text || "").trim() ||
    [(view?.desc || "").trim(), (view?.ocr_text || "").trim()].filter(Boolean).join("\n\n");
  const comments = view?.comments ?? [];
  const meta = [
    "小红书",
    view?.seller ? `作者 ${view.seller}` : null,
    view?.browse_count ? `赞 ${view.browse_count}` : null,
    view?.want_count ? `收藏 ${view.want_count}` : null,
    isVideo ? "视频（暂跳过）" : null,
  ].filter(Boolean);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,860px)] w-[min(100%-1.5rem,920px)] max-w-none flex-col gap-0 overflow-hidden p-0 sm:max-w-none">
        <DialogHeader className="shrink-0 gap-1 border-b border-border/70 px-5 py-3.5 pr-12 text-left">
          <DialogTitle className="line-clamp-2 text-sm">{title}</DialogTitle>
          {meta.length > 0 ? (
            <DialogDescription className="truncate text-xs">{meta.join(" · ")}</DialogDescription>
          ) : null}
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          {!view ? (
            <p className="text-sm text-muted-foreground">没有可展示的笔记</p>
          ) : (
            <div className="space-y-5">
              <div className="grid gap-5 md:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
                <div className="overflow-hidden rounded-lg bg-muted/40">
                  <Avatar className="aspect-[3/4] h-auto w-full rounded-none after:rounded-none">
                    {view.image_url ? (
                      <AvatarImage
                        src={view.image_url}
                        alt=""
                        className="size-full rounded-none object-cover"
                      />
                    ) : null}
                    <AvatarFallback className="size-full rounded-none text-sm">
                      暂无封面
                    </AvatarFallback>
                  </Avatar>
                </div>

                <div className="min-w-0 space-y-3">
                  <h3 className="text-base leading-snug font-medium text-foreground">{view.title}</h3>
                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="secondary">小红书</Badge>
                    {isVideo ? <Badge variant="outline">视频</Badge> : <Badge variant="outline">图文</Badge>}
                    {view.id ? (
                      <Badge variant="outline" className="font-mono text-[10px]">
                        {view.id}
                      </Badge>
                    ) : null}
                  </div>

                  {isVideo ? (
                    <p className="text-sm text-muted-foreground">
                      视频笔记暂不解析正文与 OCR，后续再支持。
                    </p>
                  ) : body ? (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                      {body}
                    </p>
                  ) : loadingDetail ? (
                    <p className="text-sm text-muted-foreground">正在加载正文与 OCR…</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">暂无正文</p>
                  )}

                  <dl className="space-y-1.5 text-sm">
                    {view.seller ? (
                      <div className="flex gap-3">
                        <dt className="w-10 shrink-0 text-muted-foreground">作者</dt>
                        <dd className="min-w-0 truncate">{view.seller}</dd>
                      </div>
                    ) : null}
                    {view.browse_count ? (
                      <div className="flex gap-3">
                        <dt className="w-10 shrink-0 text-muted-foreground">赞</dt>
                        <dd>{view.browse_count}</dd>
                      </div>
                    ) : null}
                    {view.want_count ? (
                      <div className="flex gap-3">
                        <dt className="w-10 shrink-0 text-muted-foreground">收藏</dt>
                        <dd>{view.want_count}</dd>
                      </div>
                    ) : null}
                  </dl>

                  {!isVideo && view.ocr_text?.trim() && view.content_text?.trim() ? (
                    <details className="rounded-lg bg-muted/30 px-3 py-2">
                      <summary className="cursor-pointer text-xs text-muted-foreground">
                        仅看图片 OCR
                      </summary>
                      <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
                        {view.ocr_text.trim()}
                      </p>
                    </details>
                  ) : null}
                </div>
              </div>

              <section className="space-y-3 border-t border-border/70 pt-4">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-medium text-foreground">评论</h4>
                  {comments.length > 0 ? (
                    <span className="text-xs text-muted-foreground">{comments.length} 条</span>
                  ) : null}
                </div>

                {isVideo ? (
                  <p className="text-sm text-muted-foreground">视频笔记暂不拉评论</p>
                ) : loadingDetail ? (
                  <p className="text-sm text-muted-foreground">正在加载评论…</p>
                ) : detailError ? (
                  <p className="text-sm text-muted-foreground">{detailError}</p>
                ) : comments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">暂无评论</p>
                ) : (
                  <ul className="space-y-3">
                    {comments.map((comment, index) => (
                      <li
                        key={`${comment.author}-${comment.time ?? ""}-${index}`}
                        className="rounded-lg bg-muted/40 px-3 py-2.5"
                      >
                        <div className="mb-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                          <span className="text-sm font-medium text-foreground">
                            {comment.author || "匿名"}
                          </span>
                          {comment.time ? (
                            <span className="text-[11px] text-muted-foreground">{comment.time}</span>
                          ) : null}
                        </div>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                          {comment.content}
                        </p>
                        {comment.reply ? (
                          <p className="mt-2 border-l-2 border-border pl-2 text-xs leading-relaxed text-muted-foreground">
                            回复：{comment.reply}
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border/70 px-5 py-3">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!url}
            onClick={() => {
              if (url) void openProductInBrowserTab(url);
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
