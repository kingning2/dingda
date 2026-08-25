/**
 * 桌面应用生命周期钩子。
 *
 * @author Xiaoman
 * @created 2026-08-18
 */

export { useRouteChange } from "./useRouteChange";
export { useStartApp } from "./useStartApp";
export { usePluginLifecycle } from "./usePluginLifecycle";
export { useErrorLifecycle, useErrorStore } from "./useErrorLifecycle";
export { logStartupPhase, logFirstScreenRender } from "./startup-log";
export type { ErrorState } from "./useErrorLifecycle";
