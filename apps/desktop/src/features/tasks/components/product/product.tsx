import {
  Button,
  Card,
  CardContent,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  ScrollArea,
} from "@desk/ui";
import { ExternalLink, ListTodo, Star } from "@desk/ui/icons";

import type { Product } from "../../workbench/types";

function formatPrice(price: number): string {
  return `¥${price.toLocaleString("zh-CN")}`;
}

export function ProductCard({
  product,
  onSelect,
}: {
  product: Product;
  onSelect?: (product: Product) => void;
}) {
  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-md"
      onClick={() => onSelect?.(product)}
    >
      <CardContent className="p-3">
        <div className="mb-2 flex h-24 items-center justify-center rounded-[var(--radius-md)] bg-muted/40 text-[length:var(--text-xs)] text-muted-foreground">
          {product.image ? (
            <img src={product.image} alt="" className="h-full w-full rounded-[var(--radius-md)] object-cover" />
          ) : (
            "商品图"
          )}
        </div>
        {product.condition ? (
          <span className="inline-flex rounded-full border border-border/70 px-2 py-0.5 text-[length:var(--text-xs)] text-muted-foreground">
            {product.condition}
          </span>
        ) : null}
        <p className="mt-2 line-clamp-2 text-[length:var(--text-sm)] font-medium text-foreground">
          {product.title}
        </p>
        <p className="mt-1 text-[length:var(--text-sm)] font-semibold text-primary">
          {formatPrice(product.price)}
        </p>
        <p className="mt-1 text-[length:var(--text-xs)] text-muted-foreground">
          {product.platform}
          {product.location ? ` · ${product.location}` : ""}
        </p>
        <div className="mt-2 flex items-center justify-between text-[length:var(--text-xs)] text-muted-foreground">
          <span>{product.favorites ?? 0} 人收藏</span>
          {product.aiScore != null ? <span>AI {product.aiScore}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function ProductGrid({
  products,
  onSelect,
}: {
  products: Product[];
  onSelect?: (product: Product) => void;
}) {
  if (products.length === 0) {
    return (
      <p className="py-8 text-center text-[length:var(--text-sm)] text-muted-foreground">
        暂无商品数据
      </p>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-2 xl:grid-cols-3">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} onSelect={onSelect} />
      ))}
    </div>
  );
}

export function ProductTable({
  products,
  onSelect,
}: {
  products: Product[];
  onSelect?: (product: Product) => void;
}) {
  return (
    <ScrollArea className="h-full max-h-[calc(100vh-220px)]">
      <table className="w-full text-left text-[length:var(--text-xs)]">
        <thead className="sticky top-0 bg-card text-muted-foreground">
          <tr className="border-b border-border/60">
            <th className="px-2 py-2 font-medium">商品</th>
            <th className="px-2 py-2 font-medium">成色</th>
            <th className="px-2 py-2 font-medium">价格</th>
            <th className="px-2 py-2 font-medium">平台</th>
            <th className="px-2 py-2 font-medium">城市</th>
            <th className="px-2 py-2 font-medium">收藏</th>
            <th className="px-2 py-2 font-medium">AI</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product) => (
            <tr
              key={product.id}
              className="cursor-pointer border-b border-border/40 hover:bg-muted/30"
              onClick={() => onSelect?.(product)}
            >
              <td className="max-w-[180px] truncate px-2 py-2">{product.title}</td>
              <td className="px-2 py-2">{product.condition ?? "—"}</td>
              <td className="px-2 py-2 font-medium text-primary">{formatPrice(product.price)}</td>
              <td className="px-2 py-2">{product.platform}</td>
              <td className="px-2 py-2">{product.location ?? "—"}</td>
              <td className="px-2 py-2">{product.favorites ?? "—"}</td>
              <td className="px-2 py-2">{product.aiScore ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollArea>
  );
}

export function ProductDetailDialog({
  product,
  open,
  onOpenChange,
}: {
  product: Product | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!product) {
    return null;
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{product.title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-[length:var(--text-sm)]">
          <div className="flex h-40 items-center justify-center rounded-[var(--radius-lg)] bg-muted/40 text-muted-foreground">
            商品图片
          </div>
          <p className="text-2xl font-semibold text-primary">{formatPrice(product.price)}</p>
          <div className="grid grid-cols-2 gap-2 text-[length:var(--text-xs)] text-muted-foreground">
            <span>成色：{product.condition ?? "—"}</span>
            <span>平台：{product.platform}</span>
            <span>城市：{product.location ?? "—"}</span>
            <span>收藏：{product.favorites ?? "—"}</span>
            <span>浏览：{product.views ?? "—"}</span>
            <span>AI 评分：{product.aiScore ?? "—"}</span>
            <span>风险：{product.riskScore ?? "—"}</span>
          </div>
        </div>
        <DialogFooter className="gap-2 sm:justify-start">
          {product.url ? (
            <Button type="button" size="sm" variant="outline" asChild>
              <a href={product.url} target="_blank" rel="noreferrer">
                <ExternalLink className="size-3.5" aria-hidden />
                查看原商品
              </a>
            </Button>
          ) : null}
          <Button type="button" size="sm" variant="ghost">
            <ListTodo className="size-3.5" aria-hidden />
            加入对比
          </Button>
          <Button type="button" size="sm" variant="ghost">
            <Star className="size-3.5" aria-hidden />
            收藏
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
