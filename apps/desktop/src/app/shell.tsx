/**
 * 桌面应用主壳：窗口标题栏 + 侧栏导航 + 工作区。
 *
 * @author coisini
 * @created 2026-07-20
 */

import { useEffect, useState } from "react";
import { IconButton, SidebarProvider, ThemeToggle } from "@desk/ui";
import { Settings } from "@desk/ui/icons";
import {
  closeWindow,
  getPlatform,
  minimizeWindow,
  startWindowDrag,
  subscribeWindowMaximized,
  toggleMaximizeWindow,
} from "@desk/platform";
import { SettingsDialogProvider } from "./settings";
import { PlatformShellLifecycles } from "virtual:dingda/platform-shell-lifecycles";
import { useRouteChange, useStartApp, usePluginLifecycle } from "../lifecycle";
import { AppLayout, MainPanel } from "./layout";
import { WorkspaceSidebar } from "./layout/workspace-sidebar";
import { TitleBar } from "./title-bar";
import { useWorkspaceTabs, WorkspaceNavProvider } from "./use-workspace-tabs";
import { WorkspaceOutlet } from "./workspace-outlet";

/**
 * 壳内层：依赖 {@link SettingsDialogProvider}。
 *
 * @author coisini
 * @created 2026-07-21
 *
 * @returns 壳内容节点
 */
function AppShellInner() {
  const platform = getPlatform();
  const [isMaximized, setIsMaximized] = useState(false);
  const [sidebarExpanded, setSidebarExpanded] = useState(() => {
    if (typeof window === "undefined") {
      return true;
    }
    return window.localStorage.getItem("desk.sidebar.expanded") !== "false";
  });
  const { activePath, selectTab } = useWorkspaceTabs();

  useEffect(() => {
    window.localStorage.setItem("desk.sidebar.expanded", String(sidebarExpanded));
  }, [sidebarExpanded]);

  useRouteChange();
  useStartApp();
  usePluginLifecycle();

  useEffect(() => {
    const redirects: Record<string, string> = {
      "/discovery": "/discovery/high-profit",
      "/profit": "/profit/calculator",
      "/monitoring": "/monitoring/subscriptions",
      "/settings": "/settings/general",
    };
    const next = redirects[activePath];
    if (next) {
      selectTab(next);
    }
  }, [activePath, selectTab]);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    void subscribeWindowMaximized((maximized) => {
      if (!cancelled) {
        setIsMaximized(maximized);
      }
    }).then((unsubscribe) => {
      if (cancelled) {
        unsubscribe();
        return;
      }
      unlisten = unsubscribe;
    });

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  return (
    <WorkspaceNavProvider selectTab={selectTab}>
      <PlatformShellLifecycles />
      <div className="flex h-screen w-full flex-col overflow-hidden bg-shell">
        <TitleBar
          platform={platform}
          isMaximized={isMaximized}
          actions={
            <>
              <IconButton
                label="设置"
                title="设置"
                onClick={() => selectTab("/settings/general")}
              >
                <Settings className="size-3.5" />
              </IconButton>
              <ThemeToggle size="compact" />
            </>
          }
          onStartDrag={() => void startWindowDrag()}
          onMinimize={() => void minimizeWindow()}
          onToggleMaximize={() => void toggleMaximizeWindow()}
          onClose={() => void closeWindow()}
        />
        <AppLayout
          sidebar={
            <SidebarProvider open={sidebarExpanded} setOpen={setSidebarExpanded} defaultOpen>
              <WorkspaceSidebar activePath={activePath} onNavigate={selectTab} />
            </SidebarProvider>
          }
        >
          <MainPanel>
            <WorkspaceOutlet activePath={activePath} />
          </MainPanel>
        </AppLayout>
      </div>
    </WorkspaceNavProvider>
  );
}

/**
 * 桌面应用主壳。
 *
 * 负责：窗口 TitleBar、侧栏导航、工作区内容出口、设置弹窗。
 *
 * @author coisini
 * @created 2026-07-20
 *
 * @returns 应用壳节点
 */
export function AppShell() {
  return (
    <SettingsDialogProvider>
      <AppShellInner />
    </SettingsDialogProvider>
  );
}
