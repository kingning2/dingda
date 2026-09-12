/**
 * 启动探测结果（Agent CLI + 平台账号 + 最近会话）的全局状态。
 * 预热写这里，首页 / 项目页只订阅下发。
 *
 * 为什么单独成包、且放在最底层：
 * 这份状态天然跨域 —— Agent 域写 agents、账号域写 accounts、首页域读 recentWorks。
 * 早先它挂在 ui-crawler 里，于是「谁都要引 ui-crawler」和「ui-crawler 要引 ui-agent」
 * 同时成立，直接把依赖图拧成了环。状态本身不依赖任何业务逻辑，只依赖线协议类型，
 * 所以让它下沉为叶子包，各域各自向上依赖它即可。
 */

import { create } from "zustand";

import type { AccountListItem, AccountPlatform } from "@v2/contracts/account";
import type { AgentRuntimeItem } from "@v2/contracts/agent-runtime";
import type { AgentWorkSummary } from "@v2/contracts/ai-work";

export const ACCOUNT_PLATFORMS: AccountPlatform[] = [
  "xianyu",
  "ali1688",
  "xiaohongshu",
];

export type DiscoveryState = {
  agents: AgentRuntimeItem[];
  agentsScanning: boolean;

  accounts: AccountListItem[];
  autoConnectIds: string[];
  accountsLoading: boolean;
  accountsError: string | null;
  accountsLoaded: boolean;

  /** 最近工作会话（首页 / 全部项目共用）。 */
  recentWorks: AgentWorkSummary[];
  recentWorksLoading: boolean;
  recentWorksLoaded: boolean;

  setAgents: (agents: AgentRuntimeItem[]) => void;
  setAgentsScanning: (scanning: boolean) => void;

  setAccountsSnapshot: (
    accounts: AccountListItem[],
    autoConnectIds: string[],
  ) => void;
  upsertAccount: (account: AccountListItem) => void;
  removeAccount: (accountId: string) => void;
  setAutoConnectIds: (ids: string[]) => void;
  setAccountsLoading: (loading: boolean) => void;
  setAccountsError: (error: string | null) => void;

  setRecentWorks: (works: AgentWorkSummary[]) => void;
  setRecentWorksLoading: (loading: boolean) => void;
};

export const useDiscoveryStore = create<DiscoveryState>((set) => ({
  agents: [],
  agentsScanning: false,

  accounts: [],
  autoConnectIds: [],
  accountsLoading: false,
  accountsError: null,
  accountsLoaded: false,

  recentWorks: [],
  recentWorksLoading: false,
  recentWorksLoaded: false,

  setAgents: (agents) =>
    set((state) => (state.agents === agents ? state : { agents })),
  setAgentsScanning: (agentsScanning) =>
    set((state) => (state.agentsScanning === agentsScanning ? state : { agentsScanning })),

  setAccountsSnapshot: (accounts, autoConnectIds) =>
    set({
      accounts,
      autoConnectIds,
      accountsLoaded: true,
      accountsError: null,
    }),

  upsertAccount: (account) =>
    set((state) => {
      const exists = state.accounts.some(
        (item) => item.account_id === account.account_id,
      );
      return {
        accounts: exists
          ? state.accounts.map((item) =>
              item.account_id === account.account_id ? account : item,
            )
          : [account, ...state.accounts],
      };
    }),

  removeAccount: (accountId) =>
    set((state) => ({
      accounts: state.accounts.filter((item) => item.account_id !== accountId),
      autoConnectIds: state.autoConnectIds.filter((id) => id !== accountId),
    })),

  setAutoConnectIds: (autoConnectIds) => set({ autoConnectIds }),
  setAccountsLoading: (accountsLoading) => set({ accountsLoading }),
  setAccountsError: (accountsError) => set({ accountsError }),

  setRecentWorks: (recentWorks) =>
    set({
      recentWorks,
      recentWorksLoaded: true,
      recentWorksLoading: false,
    }),
  setRecentWorksLoading: (recentWorksLoading) => set({ recentWorksLoading }),
}));

export function getDiscoveryAgents(): AgentRuntimeItem[] {
  return useDiscoveryStore.getState().agents;
}

export function getDiscoveryAccounts(platform?: AccountPlatform): AccountListItem[] {
  const accounts = useDiscoveryStore.getState().accounts;
  if (!platform) return accounts;
  return accounts.filter((item) => item.platform === platform);
}
