/**
 * 闲鱼设置分区链步骤（仅编译期启用闲鱼时由 Vite 插件 import）。
 */

import { Shield } from "@desk/ui/icons";

import { RiskLogsPanel } from "../risk-logs-panel";

import type { SettingsSectionDef } from "../types";

/** 闲鱼专属设置分区。 */
export const xianyuSettingsSections: SettingsSectionDef[] = [
  {
    id: "risk",
    label: "风控日志",
    icon: Shield,
    Panel: RiskLogsPanel,
  },
];
