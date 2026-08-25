/**
 * 设置分区链 — 插件生成的 `PLATFORM_SETTINGS_STEPS`（仅含编译期启用平台）。
 */

import { PLATFORM_SETTINGS_STEPS } from "virtual:dingda/platform-settings-steps";

import type { SettingsSectionDef } from "../types";

/** 合并平台设置分区（保持链顺序）。 */
export function mergePlatformSettingsSections(): SettingsSectionDef[] {
  return PLATFORM_SETTINGS_STEPS.flat();
}
