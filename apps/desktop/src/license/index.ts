/**
 * 软件授权公开导出 — 闸门与设置内激活面板。
 *
 * @author coisini
 * @created 2026-07-16
 */

export { LicenseGateProvider, useLicenseGateContext } from "./license-gate-context";
export { LicenseActivationPanel } from "./license-activation-panel";
export {
  formatLicenseRemaining,
  formatLicenseExpiresAt,
} from "./format-license-remaining";
export type { LicenseRemainingLabel } from "./format-license-remaining";
export { useLicenseGate } from "./use-license-gate";
export type { UseLicenseGateResult } from "./use-license-gate";
export { useLicenseActivate } from "./use-license-activate";
export type { UseLicenseActivateResult } from "./use-license-activate";
export { LicenseGateController } from "./license-gate-controller";
export { LicenseActivationService } from "./license-activation-service";
export { UnlockPage } from "./unlock/unlock-page";
export type { UnlockStatus, UnlockStep, UnlockStepState } from "./unlock/types";

import { lockedRoutePaths } from "@platform-routes";

/**
 * 判断路径是否需要授权（由路由配置中 `locked: true` 的段决定）。
 *
 * @param pathname - 当前路由路径
 */
export function isLicensedRoute(pathname: string): boolean {
  return lockedRoutePaths.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
