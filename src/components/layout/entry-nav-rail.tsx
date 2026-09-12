import {
  BarChart3,
  Bot,
  Folder,
  Home,
  LogOut,
  PanelLeftClose,
  Palette,
  ScanSearch,
  Search,
  Settings,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { NAV_ITEMS } from "@/lib/mock-data";
import { supportsExternalAgents } from "@/lib/capabilities";
import { entryPath, entryViewFromPathname } from "@/routes/paths";
import { Button } from "@v2/ui-primitives/button";
import { Kbd } from "@v2/ui-primitives/kbd";
import { Avatar, AvatarFallback } from "@v2/ui-primitives/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@v2/ui-primitives/dropdown-menu";
import { cn } from "@v2/ui-primitives/utils";

const ICON_MAP: Record<string, LucideIcon> = {
  home: Home,
  community: Users,
  folder: Folder,
  palette: Palette,
  bot: Bot,
  "user-round": UserRound,
  spider: ScanSearch,
};

interface EntryNavRailProps {
  open: boolean;
  onOpenSearch: () => void;
  onToggleRail: () => void;
}

export function EntryNavRail({ open, onOpenSearch, onToggleRail }: EntryNavRailProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const activeView = entryViewFromPathname(location.pathname);
  const showExternalAgents = supportsExternalAgents();
  const navItems = NAV_ITEMS.filter(
    (item) => !("requiresExternalAgents" in item && item.requiresExternalAgents) || showExternalAgents,
  );

  return (
    <nav
      className={cn(
        "relative z-30 flex h-full w-full min-w-0 flex-col",
        "pointer-events-none",
        open && "pointer-events-auto",
      )}
      aria-label="主导航"
      aria-hidden={!open}
    >
      <div
        className={cn(
          "mx-2.5 m-2.5 flex h-[calc(100%-10px)] min-h-0 flex-1 flex-col justify-between gap-2",
          "rounded-xl border border-transparent bg-white/65 pt-2.5 pb-[5px] shadow-sm backdrop-blur-[20px]",
        )}
      >
        <div className="flex w-full flex-col gap-1 px-2">
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              className="h-8 min-w-0 flex-1 justify-start gap-2 px-2.5 text-[13px] text-muted-foreground"
              onClick={onOpenSearch}
            >
              <Search className="size-3.5" />
              <span className="truncate">搜索项目</span>
              <Kbd className="ml-auto">⌘K</Kbd>
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={onToggleRail} aria-label="收起侧边栏">
              <PanelLeftClose className="size-4" />
            </Button>
          </div>

          <div className="mt-1 flex flex-col gap-0.5">
            {navItems.map((item) => {
              const Icon = ICON_MAP[item.icon] ?? Home;
              const active = activeView === item.id;
              return (
                <Button
                  key={item.id}
                  variant={active ? "secondary" : "ghost"}
                  className={cn(
                    "h-9 w-full justify-start gap-2.5 px-2.5 text-[13px] font-medium",
                    active && "bg-accent/30 text-accent-foreground",
                  )}
                  onClick={() => navigate(entryPath(item.id))}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon className="size-4 shrink-0" />
                  <span>{item.label}</span>
                </Button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-1 px-2">
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" className="h-auto w-full justify-start gap-2 px-2 py-1.5" />
              }
            >
              <Avatar className="size-7">
                <AvatarFallback className="bg-primary text-xs text-primary-foreground">叮</AvatarFallback>
              </Avatar>
              <span className="min-w-0 flex-1 truncate text-left text-[13px] font-medium">叮答用户</span>
              <Settings className="size-3.5 shrink-0 text-muted-foreground" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" side="top" className="w-48">
              <DropdownMenuItem onClick={() => navigate(entryPath("accounts"))}>
                <Settings className="size-4" />
                账号
              </DropdownMenuItem>
              <DropdownMenuItem>
                <BarChart3 className="size-4" />
                用量
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive">
                <LogOut className="size-4" />
                退出登录
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </nav>
  );
}
