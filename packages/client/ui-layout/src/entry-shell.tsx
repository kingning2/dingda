import { useState } from "react";
import { AnimatedOutlet } from "@web/routes/animated-outlet";
import { PageHeader } from "./page-header";
import { EntryNavRail } from "./entry-nav-rail";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@v2/ui-primitives/dialog";
import { Input } from "@v2/ui-primitives/input";
import { cn } from "@v2/ui-primitives/utils";

interface EntryShellProps {
  railOpen: boolean;
  onToggleRail: () => void;
  /** 全宽铺满主区域（AI 工作详情等）：不渲染入口侧栏。 */
  fullBleed?: boolean;
  /** 由路由 handle.title 注入的页面标题。 */
  pageTitle?: string;
}

export function EntryShell({
  railOpen,
  onToggleRail,
  fullBleed = false,
  pageTitle,
}: EntryShellProps) {
  const [searchOpen, setSearchOpen] = useState(false);

  if (fullBleed) {
    return (
      <div className="relative flex h-full min-h-0 flex-col bg-transparent">
        <main className="h-full min-h-0 min-w-0 overflow-hidden">
          <AnimatedOutlet className="h-full min-h-0" />
        </main>
      </div>
    );
  }

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-transparent">
      <div
        className={cn(
          "grid h-full min-h-0 flex-1 transition-[grid-template-columns] duration-200",
          railOpen
            ? "grid-cols-[var(--entry-rail-width)_minmax(0,1fr)]"
            : "grid-cols-[0_minmax(0,1fr)]",
        )}
        style={{ transitionTimingFunction: "cubic-bezier(0.23, 1, 0.32, 1)" }}
      >
        <aside className="h-full min-w-0 overflow-hidden">
          <EntryNavRail
            open={railOpen}
            onOpenSearch={() => setSearchOpen(true)}
            onToggleRail={onToggleRail}
          />
        </aside>

        <main className="h-full min-h-0 min-w-0 overflow-y-auto overflow-x-hidden">
          <div className="mx-auto w-full max-w-[1440px] px-6 pb-8">
            {pageTitle ? <PageHeader title={pageTitle} /> : null}
            <AnimatedOutlet />
          </div>
        </main>
      </div>

      <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>搜索项目</DialogTitle>
          </DialogHeader>
          <Input type="search" placeholder="输入关键词…" autoFocus />
        </DialogContent>
      </Dialog>
    </div>
  );
}
