/**
 * 设置分区类型。
 */

import type { ComponentType } from "react";
import type { LucideIcon } from "@desk/ui/icons";

/** 设置分区 id。 */
export type SettingsSectionId = "license" | "plugins" | "risk" | "disclaimer" | "about";

/** 单个设置分区定义。 */
export interface SettingsSectionDef {
  id: SettingsSectionId;
  label: string;
  icon: LucideIcon;
  Panel: ComponentType;
}
