/**
 * 工作区侧栏 — Aceternity Sidebar + 可折叠菜单分组。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */

import { useMemo } from "react";
import { CHANNEL_MANAGE_ROOT, managePath } from "@desk/platform/compile";
import {
  DesktopSidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupsProvider,
  SidebarHeader,
  SidebarLink,
  SidebarToggle,
} from "@desk/ui";
import { Home } from "@desk/ui/icons";
import { manageNavGroups, type ManageNavItem } from "@platform-routes";
import { aiFeature } from "@feature/agent";
import { chatFeature } from "@feature/chat";

const GROUP_STORAGE_KEY = "desk.sidebar.groups";
/** 首次使用默认展开的分组（其余默认收起）。 */
const DEFAULT_OPEN_GROUPS = ["交易"];

/**
 * 工作区侧栏属性。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */
export interface WorkspaceSidebarProps {
  /** 当前激活路径。 */
  activePath: string;
  /** 选择标签页/路由。 */
  onNavigate: (path: string) => void;
}

function isNavActive(activePath: string, targetPath: string): boolean {
  if (targetPath === "/") {
    return activePath === "/";
  }
  return activePath === targetPath || activePath.startsWith(`${targetPath}/`);
}

/**
 * 桌面工作区左侧导航。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */
export function WorkspaceSidebar({ activePath, onNavigate }: WorkspaceSidebarProps) {
  const AiNavIcon = aiFeature.navItem.icon;
  const ChatNavIcon = chatFeature.navItem.icon;
  const autoOpenGroupIds = useMemo(
    () =>
      manageNavGroups
        .filter((group) =>
          group.items.some((item) => isNavActive(activePath, managePath(item.key))),
        )
        .map((group) => group.label),
    [activePath],
  );

  return (
    <DesktopSidebar className="min-h-0">
      <div className="flex h-full min-h-0 flex-col">
        <SidebarHeader>
          <SidebarLink
            label="首页"
            icon={<Home className="size-[1.125rem]" aria-hidden />}
            active={
              activePath === CHANNEL_MANAGE_ROOT ||
              activePath === managePath("dashboard") ||
              activePath === "/"
            }
            onClick={() => onNavigate(CHANNEL_MANAGE_ROOT)}
          />
          <SidebarLink
            label={chatFeature.navItem.label}
            icon={<ChatNavIcon className="size-[1.125rem]" aria-hidden />}
            active={isNavActive(activePath, chatFeature.path)}
            onClick={() => onNavigate(chatFeature.path)}
          />
        </SidebarHeader>

        <SidebarGroupsProvider
          storageKey={GROUP_STORAGE_KEY}
          defaultOpenGroupIds={DEFAULT_OPEN_GROUPS}
          autoOpenGroupIds={autoOpenGroupIds}
        >
          <SidebarContent>
            {manageNavGroups.map((group) => {
              const GroupIcon = group.icon;
              return (
              <SidebarGroup
                key={group.label}
                groupId={group.label}
                label={group.label}
                icon={
                  GroupIcon ? (
                    <GroupIcon className="size-[1.125rem]" aria-hidden />
                  ) : undefined
                }
              >
                {group.items.map((item: ManageNavItem) => {
                  const path = managePath(item.key);
                  const Icon = item.icon;
                  return (
                    <SidebarLink
                      key={item.key}
                      label={item.label}
                      icon={<Icon className="size-[1.125rem]" aria-hidden />}
                      active={isNavActive(activePath, path)}
                      onClick={() => onNavigate(path)}
                    />
                  );
                })}
              </SidebarGroup>
              );
            })}
          </SidebarContent>
        </SidebarGroupsProvider>

        <SidebarFooter className="mt-auto space-y-2 border-t border-border pt-2">
          <SidebarLink
            label={aiFeature.navItem.label}
            icon={<AiNavIcon className="size-[1.125rem]" aria-hidden />}
            active={isNavActive(activePath, aiFeature.path)}
            onClick={() => onNavigate(aiFeature.path)}
          />
          <SidebarToggle placement="footer" />
        </SidebarFooter>
      </div>
    </DesktopSidebar>
  );
}
