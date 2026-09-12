import { Home, PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import { Button } from "@v2/ui-primitives/button";
import { Separator } from "@v2/ui-primitives/separator";
import { cn } from "@v2/ui-primitives/utils";

interface WorkspaceTabsBarProps {
  railOpen: boolean;
  onToggleRail: () => void;
  title?: string;
}

export function WorkspaceTabsBar({
  railOpen,
  onToggleRail,
  title = "首页",
}: WorkspaceTabsBarProps) {
  return (
    <header className={cn("flex h-11 w-full min-w-0 items-center gap-2 bg-background px-2.5 pl-2 select-none")}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={onToggleRail}
        className="h-[30px] shrink-0 gap-1.5 bg-accent/30 text-accent-foreground"
        aria-label={railOpen ? "收起侧边栏" : "展开侧边栏"}
        aria-pressed={railOpen}
      >
        {railOpen ? <PanelLeftClose className="size-3.5" /> : <PanelLeftOpen className="size-3.5" />}
        <Home className="size-3.5" />
        <span>{title}</span>
      </Button>

      <Separator orientation="vertical" className="h-7" />

      <div className="min-w-0 flex-1" />

      <Button type="button" variant="ghost" size="icon-sm" aria-label="新建">
        <Plus className="size-4" />
      </Button>
    </header>
  );
}
