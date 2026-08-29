/**
 * 闲鱼账号管理页（薄入口）— 构造闲鱼平台能力并注入共享面板。
 *
 * 共享组件不感知平台；本站仅把「连接 / 自动连接 / 文案」作为方法注入。
 * 双站构建时与 1688 共享账号管理页 Tab；单站构建时仅渲染闲鱼面板。
 *
 * @author Xiaoman
 * @created 2026-08-13
 */

import { AccountsHubPage } from "@components/accounts";
import type { AccountPanelDeps, AccountsTab } from "@components/accounts";
import type { AccountPlatform } from "@desk/platform/ipc/account";
import {
  accountConnect,
  accountDisconnect,
  accountConnectionState,
} from "@desk/platform/ipc/account";
import {
  loadAutoConnectConfig,
  runAutoConnectNow,
  setAccountAutoConnect,
  setAutoConnectOnStartEnabled,
} from "@components/accounts/use-auto-connect";
import { ali1688AccountTab } from "@feature/platform/ali1688/accounts";
import { xiaohongshuAccountTab } from "@feature/platform/xiaohongshu/accounts";

const xianyuDeps: AccountPanelDeps = {
  platform: "xianyu",
  platformName: "闲鱼",
  appName: "闲鱼",
  supportsConnection: true,
  connect: (ownerId, accountId) => accountConnect(ownerId, accountId),
  disconnect: (ownerId, accountId) => accountDisconnect(ownerId, accountId),
  connectionState: (ownerId, accountId) => accountConnectionState(ownerId, accountId),
  autoConnect: {
    load: loadAutoConnectConfig,
    setEnabled: setAutoConnectOnStartEnabled,
    setAccount: setAccountAutoConnect,
    runNow: runAutoConnectNow,
  },
};

/** 闲鱼账号管理页 Tab 配置（供双站 Hub 组装）。 */
export const xianyuAccountTab: AccountsTab = {
  id: "xianyu",
  label: "闲鱼账号",
  deps: xianyuDeps,
};

/** 本构建启用的账号管理 Tab（按平台 feature 门控）。 */
const ENABLED_ACCOUNT_TABS: AccountsTab[] = [
  xianyuAccountTab,
  ...(__DINGDA_HAS_ALI1688__ ? [ali1688AccountTab] : []),
  ...(__DINGDA_HAS_XIAOHONGSHU__ ? [xiaohongshuAccountTab] : []),
];

/**
 * 账号管理页（默认闲鱼 Tab；双站构建时含 1688 Tab）。
 *
 * 深链 `/manage/accounts-1688` 传 `initialTab="ali1688"` 定位 1688 Tab。
 *
 * @author Xiaoman
 * @created 2026-08-13
 */
export function XianyuAccountsPage({
  initialTab = "xianyu",
  embedded = false,
}: {
  initialTab?: AccountPlatform;
  /** 嵌入设置路由时不渲染账号页大标题。 */
  embedded?: boolean;
}) {
  return (
    <AccountsHubPage tabs={ENABLED_ACCOUNT_TABS} initialTab={initialTab} embedded={embedded} />
  );
}
