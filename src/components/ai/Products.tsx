/**
 * 右侧爬取结果：一次展示全部，虚拟滚动保性能。
 * 点击商品打开自绘详情 Modal。
 */

import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ExternalLink } from "lucide-react";
import type {
  AgentWorkComparisonView,
  AgentWorkProductItem,
  AgentWorkProductsView,
} from "@v2/contracts/ai-work";
import { Avatar, AvatarFallback, AvatarImage } from "@v2/ui-primitives/avatar";
import { Badge } from "@v2/ui-primitives/badge";
import { Card, CardContent, CardDescription, CardTitle } from "@v2/ui-primitives/card";
import { cn } from "@v2/ui-primitives/utils";
import { openProductPreview } from "@/lib/product-preview";
import { ComparisonResults } from "./ComparisonResults";

/** 单行预估高度（含间距）。 */
const ROW_ESTIMATE_PX = 112;
const ROW_GAP_PX = 12;

interface ProductsProps {
  products: AgentWorkProductsView;
  comparison?: AgentWorkComparisonView | null;
  className?: string;
}

function ProductRow({
  item,
  onOpen,
}: {
  item: AgentWorkProductItem;
  onOpen: (item: AgentWorkProductItem) => void;
}) {
  const meta = [
    item.platform,
    item.seller,
    item.want_count ? `想要 ${item.want_count}` : null,
    item.browse_count ? `赞 ${item.browse_count}` : null,
  ].filter(Boolean);

  return (
    <Card
      size="sm"
      className="cursor-pointer ring-border/70 transition hover:ring-primary/40"
      onClick={() => onOpen(item)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(item);
        }
      }}
      role="button"
      tabIndex={0}
    >
      <CardContent className="flex gap-3">
        <Avatar className="size-16 shrink-0 rounded-md after:rounded-md">
          {item.image_url ? <AvatarImage src={item.image_url} alt="" className="rounded-md" /> : null}
          <AvatarFallback className="rounded-md text-[10px]">图</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <CardTitle className="line-clamp-2 text-sm leading-snug">{item.title}</CardTitle>
          <p className="mt-1 text-base font-semibold text-foreground">{item.price || "—"}</p>
          {meta.length > 0 ? (
            <CardDescription className="mt-0.5 truncate text-xs">{meta.join(" · ")}</CardDescription>
          ) : null}
          <p className="mt-1 flex items-center gap-1 text-[11px] text-primary">
            <ExternalLink className="size-3 shrink-0" />
            查看详情
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function ProductVirtualList({
  items,
  onOpen,
}: {
  items: AgentWorkProductItem[];
  onOpen: (item: AgentWorkProductItem) => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_ESTIMATE_PX,
    overscan: 8,
    gap: ROW_GAP_PX,
  });

  return (
    <div ref={parentRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
      <div className="relative w-full" style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((row) => {
          const item = items[row.index];
          if (!item) return null;
          return (
            <div
              key={item.id}
              data-index={row.index}
              ref={virtualizer.measureElement}
              className="absolute top-0 left-0 w-full"
              style={{ transform: `translateY(${row.start}px)` }}
            >
              <ProductRow item={item} onOpen={onOpen} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 右侧固定结果面板。 */
export function Products({ products, comparison, className }: ProductsProps) {
  const { items, total, status } = products;

  if (comparison) {
    return <ComparisonResults comparison={comparison} />;
  }

  return (
    <div className={cn("flex h-full min-h-0 flex-col", className)}>
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-border/70 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">爬取结果</h2>
          <p className="truncate text-xs text-muted-foreground">
            {status.hint ?? "本任务抓到的商品 / 笔记"}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-0.5">
          <Badge className={cn("h-auto rounded-full border-transparent", status.badge_class)}>
            {status.label}
          </Badge>
          {total > 0 ? (
            <span className="text-xs text-muted-foreground">共 {total} 条</span>
          ) : null}
        </div>
      </header>

      {items.length === 0 ? (
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <Card className="border-dashed ring-0">
            <CardContent className="py-16 text-center text-sm text-muted-foreground">
              {status.hint ?? "开始爬取后，这里会固定展示结果列表"}
            </CardContent>
          </Card>
        </div>
      ) : (
        <ProductVirtualList items={items} onOpen={openProductPreview} />
      )}
    </div>
  );
}
