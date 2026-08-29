/**
 * 小红书账号管理页（薄入口）— 构造小红书平台能力并注入共享面板。
 *
 * 小红书无渠道 WS：面板展示扫码登录与账号列表，不提供「连接 / 断开」。
 */

import { AccountsHubPage } from "@components/accounts";
import type { AccountPanelDeps, AccountsTab } from "@components/accounts";

const xiaohongshuDeps: AccountPanelDeps = {
  platform: "xiaohongshu",
  platformName: "小红书",
  appName: "小红书",
  supportsConnection: false,
};

/** 小红书账号管理页 Tab 配置（供 Hub 组装）。 */
export const xiaohongshuAccountTab: AccountsTab = {
  id: "xiaohongshu",
  label: "小红书账号",
  deps: xiaohongshuDeps,
};

/**
 * 账号管理页（默认小红书 Tab，兼容深链）。
 */
export function XiaohongshuAccountsPage() {
  return <AccountsHubPage tabs={[xiaohongshuAccountTab]} initialTab="xiaohongshu" />;
}
