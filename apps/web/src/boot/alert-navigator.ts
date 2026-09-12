/**
 * 把 SPA 路由跳转注入给全局告警（@v2/runtime/app-alert）。
 *
 * 基座包与 UI 包都不依赖 react-router，路由实例属于应用层，所以在这里注入 ——
 * 套路同 `installGlobalErrorReporting()` 与 http-client 的 `setApiBaseUrl`。
 *
 * 注意本应用用的是 `createHashRouter`（URL 形如 `/#/accounts`），
 * 所以告警里的 `href` 必须走 `router.navigate`，整页跳转会丢掉路由。
 */

import { setAppAlertNavigator } from "@v2/runtime/app-alert";
import { router } from "@web/routes/router";

let installed = false;

export function installAppAlertNavigator(): void {
  if (installed) return;
  installed = true;
  setAppAlertNavigator((href) => {
    void router.navigate(href);
  });
}
