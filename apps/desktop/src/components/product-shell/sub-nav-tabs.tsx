/**
 * 二级导航 Tab（Button 组，无新依赖）。
 */

import { Button } from "@desk/ui";
import { useWorkspaceNav } from "../../app/use-workspace-tabs";

export interface SubNavTab {
  path: string;
  label: string;
}

export interface SubNavTabsProps {
  tabs: SubNavTab[];
  activePath: string;
}

/** 路由二级 Tab：active 用 secondary，其余 ghost。 */
export function SubNavTabs({ tabs, activePath }: SubNavTabsProps) {
  const { selectTab } = useWorkspaceNav();

  return (
    <nav className="flex flex-wrap gap-1" aria-label="二级导航">
      {tabs.map((tab) => {
        const active =
          activePath === tab.path || activePath.startsWith(`${tab.path}/`);
        return (
          <Button
            key={tab.path}
            type="button"
            size="sm"
            variant={active ? "secondary" : "ghost"}
            onClick={() => selectTab(tab.path)}
          >
            {tab.label}
          </Button>
        );
      })}
    </nav>
  );
}
