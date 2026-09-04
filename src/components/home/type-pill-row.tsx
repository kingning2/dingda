import {
  BarChart3,
  FileText,
  Image,
  Layers,
  Layout,
  Plus,
  Presentation,
  Smartphone,
  Video,
  type LucideIcon,
} from "lucide-react";
import { HOME_TYPE_CHIPS, type HomeTypeChipId } from "@/lib/mock-data";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const CHIP_ICONS: Record<string, LucideIcon> = {
  layout: Layout,
  presentation: Presentation,
  layers: Layers,
  video: Video,
  image: Image,
  "bar-chart-3": BarChart3,
  smartphone: Smartphone,
  "file-text": FileText,
  plus: Plus,
};

interface TypePillRowProps {
  activeChipId: HomeTypeChipId;
  onPick: (id: HomeTypeChipId) => void;
}

export function TypePillRow({ activeChipId, onPick }: TypePillRowProps) {
  return (
    <div className="flex w-full max-w-[720px] flex-wrap items-center justify-center gap-1.5 px-3">
      {HOME_TYPE_CHIPS.map((chip) => {
        const Icon = CHIP_ICONS[chip.icon] ?? Layout;
        const active = activeChipId === chip.id;
        return (
          <Button
            key={chip.id}
            type="button"
            variant={active ? "secondary" : "outline"}
            size="sm"
            className={cn(
              "h-[34px] rounded-full px-[11px] text-[13px]",
              active && "border-accent/40 bg-accent/30 text-accent-foreground",
            )}
            onClick={() => onPick(chip.id)}
            aria-pressed={active}
          >
            <Icon className="size-3.5" />
            {chip.label}
          </Button>
        );
      })}
    </div>
  );
}
