import type { AccountPlatform } from "@v2/contracts/account";

export interface AccountPanelConfig {
  platform: AccountPlatform;
  platformName: string;
  appName: string;
  /** 闲鱼有渠道 WS，展示连接/断开；1688 / 小红书仅展示登录态。 */
  supportsConnection: boolean;
  /** 闲鱼支持启动自动连接勾选。 */
  supportsAutoConnect?: boolean;
}

export interface AccountsTab {
  id: AccountPlatform;
  label: string;
  config: AccountPanelConfig;
}

export type { AccountListItem, AccountSessionView, AccountActionsView } from "@v2/contracts/account";
