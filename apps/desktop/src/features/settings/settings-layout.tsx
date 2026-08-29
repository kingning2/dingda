/**
 * 设置统一壳 — 仅二级 Tab，无页面大标题（各子页一致）。
 */

import type { ReactNode } from "react";
import { ScrollArea } from "@desk/ui";
import { SubNavTabs } from "@components/product-shell";
import { useLocation } from "react-router";
import { SETTINGS_TABS } from "./settings-tabs";

export function SettingsLayoutPage({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 border-b border-border px-3 py-2">
        <SubNavTabs tabs={[...SETTINGS_TABS]} activePath={pathname} />
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-4 p-3 sm:p-4">{children}</div>
      </ScrollArea>
    </div>
  );
}
