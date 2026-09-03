import type { AgentWorkProductItem } from "@/contracts/ai-work";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const CARD_WIDTH = 132;
const IMAGE_WIDTH = 116;
const IMAGE_HEIGHT = 72;

export interface ProductCardItem {
  id: string;
  title: string;
  price: string;
  image_url?: string | null;
}

export function toProductCardItem(item: AgentWorkProductItem): ProductCardItem {
  return {
    id: item.id,
    title: item.title,
    price: item.price,
    image_url: item.image_url,
  };
}

interface ProductCardProps {
  item: ProductCardItem;
  className?: string;
}

export function ProductCard({ item, className }: ProductCardProps) {
  return (
    <Card
      size="sm"
      className={cn("shrink-0 gap-1.5 py-2 ring-border/80 [--card-spacing:--spacing(2)]", className)}
      style={{ width: CARD_WIDTH }}
    >
      <CardContent className="flex flex-col gap-1.5 px-2">
        <Avatar
          className="rounded-md after:rounded-md"
          style={{ width: IMAGE_WIDTH, height: IMAGE_HEIGHT }}
        >
          {item.image_url ? <AvatarImage src={item.image_url} alt="" className="rounded-md" /> : null}
          <AvatarFallback className="rounded-md text-[10px]">图</AvatarFallback>
        </Avatar>
        <p
          className="line-clamp-2 text-[11px] font-medium leading-[14px] text-foreground"
          style={{ height: 28 }}
        >
          {item.title}
        </p>
        <p className="truncate text-xs font-semibold leading-4 text-foreground">{item.price}</p>
      </CardContent>
    </Card>
  );
}

interface ProductCardStripProps {
  items: ProductCardItem[];
  className?: string;
}

export function ProductCardStrip({ items, className }: ProductCardStripProps) {
  if (items.length === 0) return null;

  return (
    <div className={cn("mt-2 overflow-x-auto px-2.5 pb-2.5 pt-0.5", className)}>
      <div className="flex w-max min-w-full gap-2 pr-2.5">
        {items.map((item) => (
          <ProductCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}
