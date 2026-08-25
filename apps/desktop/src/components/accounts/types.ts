/**
 * 账号管理共享层 — 平台专属行为的依赖注入契约。
 *
 * 共享组件（`accounts-panel` / `accounts-hub`）内部**不做平台分支**；
 * 平台差异全部作为方法 / 配置注入（见 [`AccountPanelDeps`]）。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */

import type { AccountPlatform } from "@desk/platform/ipc/account";

/**
 * 启动自动连接能力（闲鱼 / 1688 共用勾选列表；实际渠道连接仅闲鱼）。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */
export interface AutoConnectApi {
  /** 读取自动连接配置（总开关 + 勾选账号）。 */
  load(): Promise<{ enabled: boolean; accountIds: string[] }>;
  /** 写入总开关。 */
  setEnabled(enabled: boolean): Promise<void>;
  /** 切换单个账号是否参与自动连接；返回更新后的勾选列表。 */
  setAccount(accountId: string, selected: boolean): Promise<string[]>;
  /** 立刻对勾选账号执行一轮自动连接；返回发起连接的数量。 */
  runNow(): Promise<number>;
}

/**
 * 平台账号面板所需注入的「平台专属能力」。
 *
 * 无对应能力时字段留空 / `undefined`，共享面板自动隐藏相关 UI 与调用。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */
export interface AccountPanelDeps {
  /** 平台 id（IPC 传参 / 账号过滤用，是数据而非分支依据）。 */
  platform: AccountPlatform;
  /** 平台中文名（空态 / 提示文案，如「闲鱼」「1688」）。 */
  platformName: string;
  /** 扫码 App 名（如「闲鱼」「手机淘宝 / 1688」）。 */
  appName: string;
  /** 是否有真实渠道 WS；无则 UI 展示登录态探针，不提供连接/断开。 */
  supportsConnection: boolean;
  /** 建立渠道连接，返回后端连接状态串。 */
  connect?: (ownerId: number, accountId: string) => Promise<string>;
  /** 断开渠道连接。 */
  disconnect?: (ownerId: number, accountId: string) => Promise<void>;
  /** 查询渠道连接状态串。 */
  connectionState?: (ownerId: number, accountId: string) => Promise<string>;
  /** 启动自动连接能力（可选，缺省隐藏自动连接 UI）。 */
  autoConnect?: AutoConnectApi;
}

/**
 * 账号管理页内 Tab（由平台薄入口注入到共享 Hub）。
 *
 * @author Xiaoman
 * @created 2026-08-22
 */
export interface AccountsTab {
  /** Tab 平台 id。 */
  id: AccountPlatform;
  /** Tab 文案（如「闲鱼账号」「1688账号」）。 */
  label: string;
  /** 本平台面板依赖。 */
  deps: AccountPanelDeps;
}
