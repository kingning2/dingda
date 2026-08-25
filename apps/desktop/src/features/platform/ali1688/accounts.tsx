/**
 * 1688 账号管理页（薄入口）— 构造 1688 平台能力并注入共享面板。
 *
 * 1688 无渠道 WS：面板展示登录态探针结果，不提供「连接 / 断开」。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */

import { AccountsHubPage } from "@components/accounts";
import type { AccountPanelDeps, AccountsTab } from "@components/accounts";

const ali1688Deps: AccountPanelDeps = {
  platform: "ali1688",
  platformName: "1688",
  appName: "手机淘宝 / 1688",
  supportsConnection: false,
};

/** 1688 账号管理页 Tab 配置（供双站 Hub 组装）。 */
export const ali1688AccountTab: AccountsTab = {
  id: "ali1688",
  label: "1688账号",
  deps: ali1688Deps,
};

/**
 * 账号管理页（默认 1688 Tab，兼容旧路由）。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */
export function Ali1688AccountsPage() {
  return <AccountsHubPage tabs={[ali1688AccountTab]} initialTab="ali1688" />;
}
