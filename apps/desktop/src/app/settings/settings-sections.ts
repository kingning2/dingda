/**
 * 设置弹窗分区注册表 — map 驱动侧栏与内容区渲染。
 *
 * 平台专属分区由各站 `platform-sections/*` 链式追加。
 *
 * @author Xiaoman
 * @created 2026-08-20
 */

import { AlertTriangle, Info, Key, Package } from "@desk/ui/icons";
import { LicenseActivationPanel } from "@license";
import { PluginsPanel } from "./plugin";

import { AboutPanel } from "./about-panel";
import { DisclaimerPanel } from "./disclaimer-panel";
import { mergePlatformSettingsSections } from "./platform-sections";
import type { SettingsSectionDef, SettingsSectionId } from "./types";

export type { SettingsSectionDef, SettingsSectionId } from "./types";

/** 设置弹窗分区列表（顺序即侧栏顺序）。 */
export const SETTINGS_SECTIONS: SettingsSectionDef[] = [
  {
    id: "license",
    label: "激活",
    icon: Key,
    Panel: LicenseActivationPanel,
  },
  {
    id: "plugins",
    label: "插件",
    icon: Package,
    Panel: PluginsPanel,
  },
  ...mergePlatformSettingsSections(),
  {
    id: "disclaimer",
    label: "免责声明",
    icon: AlertTriangle,
    Panel: DisclaimerPanel,
  },
  {
    id: "about",
    label: "关于",
    icon: Info,
    Panel: AboutPanel,
  },
];

/** 按 id 查找设置分区。 */
export function resolveSettingsSection(id: SettingsSectionId): SettingsSectionDef {
  return SETTINGS_SECTIONS.find((section) => section.id === id) ?? SETTINGS_SECTIONS[0];
}
