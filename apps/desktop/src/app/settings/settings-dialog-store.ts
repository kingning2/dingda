/**
 * 设置弹窗 Context 定义与 hook。
 *
 * @author coisini
 * @created 2026-07-21
 */

import { createContext, useContext } from "react";
import type { SettingsSectionId } from "./settings-sections";

/**
 * 设置弹窗上下文值。
 *
 * @author coisini
 * @created 2026-07-21
 */
export interface SettingsDialogContextValue {
  /** 是否打开。 */
  open: boolean;
  /** 打开设置弹窗，可选定位到指定分区。 */
  openSettings: (section?: SettingsSectionId) => void;
  /** 关闭设置弹窗。 */
  closeSettings: () => void;
  /** 设置打开状态。 */
  setOpen: (open: boolean) => void;
}

export const SettingsDialogContext = createContext<SettingsDialogContextValue | null>(null);

/**
 * 读取设置弹窗开关。
 *
 * @author coisini
 * @created 2026-07-21
 *
 * @returns 上下文值
 * @throws 未包裹 SettingsDialogProvider 时抛错
 */
export function useSettingsDialog(): SettingsDialogContextValue {
  const ctx = useContext(SettingsDialogContext);
  if (!ctx) {
    throw new Error("useSettingsDialog must be used within SettingsDialogProvider");
  }
  return ctx;
}
