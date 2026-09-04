import { Card, CardContent, CardDescription } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function MockPagePreview({
  title,
  focusLabel,
}: {
  title: string;
  focusLabel?: string | null;
}) {
  return (
    <div className="space-y-3 p-4">
      <div className="h-8 w-2/5 rounded-md bg-muted" />
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Card
            key={index}
            size="sm"
            className={cn(
              "ring-border/70",
              focusLabel && index === 1 ? "border-sky-400/70 ring-2 ring-sky-400/30" : undefined,
            )}
          >
            <CardContent className="space-y-2">
              <div className="aspect-[4/3] rounded-md bg-muted" />
              <div className="h-3 w-4/5 rounded bg-muted" />
              <div className="h-3 w-1/3 rounded bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
      <CardDescription className="text-center text-[11px]">
        模拟预览 · {title}
        {focusLabel ? ` · 焦点：${focusLabel}` : ""}
      </CardDescription>
    </div>
  );
}
