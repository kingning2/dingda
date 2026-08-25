/**
 * 设置弹窗 Provider — 挂载 Dialog 并暴露开关。
 *
 * @author coisini
 * @created 2026-07-21
 */

import { useCallback, useMemo, useState, type ReactNode } from "react";

import { SettingsDialog } from "./settings-dialog";
import {
  SettingsDialogContext,
  type SettingsDialogContextValue,
} from "./settings-dialog-store";
import type { SettingsSectionId } from "./settings-sections";

/**
 * 设置弹窗 Provider。
 *
 * @author coisini
 * @created 2026-07-21
 *
 * @param props - children
 * @returns Provider 节点
 */
export function SettingsDialogProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [initialSection, setInitialSection] = useState<SettingsSectionId | undefined>();

  const openSettings = useCallback((section?: SettingsSectionId) => {
    setInitialSection(section);
    setOpen(true);
  }, []);
  const closeSettings = useCallback(() => setOpen(false), []);

  const value = useMemo<SettingsDialogContextValue>(
    () => ({ open, openSettings, closeSettings, setOpen }),
    [open, openSettings, closeSettings],
  );

  return (
    <SettingsDialogContext.Provider value={value}>
      {children}
      <SettingsDialog
        open={open}
        initialSection={initialSection}
        onOpenChange={setOpen}
      />
    </SettingsDialogContext.Provider>
  );
}
