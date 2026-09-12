/**
 * 应用主壳：自定义标题栏 + 内容区（OpenDesign 浅色风格）。
 */

import { useEffect, useState, type ReactNode } from "react";
import {
  closeWindow,
  getPlatform,
  minimizeWindow,
  startWindowDrag,
  subscribeWindowMaximized,
  toggleMaximizeWindow,
} from "@v2/runtime/window";
import { TitleBar } from "./title-bar";

export function AppShell({ children }: { children: ReactNode }) {
  const platform = getPlatform();
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let unlisten: (() => void) | undefined;

    void subscribeWindowMaximized((maximized) => {
      if (!cancelled) setIsMaximized(maximized);
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
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-transparent">
      <TitleBar
        platform={platform}
        isMaximized={isMaximized}
        onStartDrag={() => void startWindowDrag()}
        onMinimize={() => void minimizeWindow()}
        onToggleMaximize={() => void toggleMaximizeWindow()}
        onClose={() => void closeWindow()}
      />
      <main className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">{children}</main>
    </div>
  );
}
