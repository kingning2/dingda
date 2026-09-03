import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface WorkStatusBadgeProps {
  label: string;
  badgeClass: string;
  hint?: string | null;
  className?: string;
}

/** 后端返回的状态徽章（label + badge_class）。 */
export function WorkStatusBadge({ label, badgeClass, hint, className }: WorkStatusBadgeProps) {
  return (
    <div className={cn("flex flex-col items-end gap-0.5", className)}>
      <Badge className={cn("h-auto rounded-full border-transparent", badgeClass)}>{label}</Badge>
      {hint ? <span className="max-w-[220px] text-right text-[11px] text-muted-foreground">{hint}</span> : null}
    </div>
  );
}
