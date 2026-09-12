import type {
  AccountActionsView,
  AccountListItem,
  AccountAuthProbeResponse,
  AccountQrCheckResponse,
  AccountSessionView,
} from "@v2/contracts/account";
import type { AccountPanelConfig, AccountsTab } from "./types";

/** 模拟 Python 返回的会话态（仅供 UI 开发占位）。 */
export const MOCK_SESSIONS = {
  connected: {
    state: "connected",
    label: "已连接",
    hint: null,
    badge_class: "bg-emerald-500/15 text-emerald-600",
  },
  disconnected: {
    state: "disconnected",
    label: "未连接",
    hint: null,
    badge_class: "bg-muted text-muted-foreground",
  },
  connecting: {
    state: "connecting",
    label: "连接中",
    hint: "正在连接闲鱼…",
    badge_class: "bg-amber-500/15 text-amber-600",
  },
  loggedIn: {
    state: "connected",
    label: "已登录",
    hint: null,
    badge_class: "bg-emerald-500/15 text-emerald-600",
  },
  notLoggedIn: {
    state: "disconnected",
    label: "未登录",
    hint: null,
    badge_class: "bg-muted text-muted-foreground",
  },
  authExpired: {
    state: "auth_expired",
    label: "登录过期",
    hint: "登录态已过期，请重新扫码",
    badge_class: "bg-orange-500/15 text-orange-700",
  },
} satisfies Record<string, AccountSessionView>;

function makeAccount(item: AccountListItem): AccountListItem {
  return item;
}

export const MOCK_ACCOUNTS: AccountListItem[] = [
  makeAccount({
    account_id: "xy:demo-shop-01",
    display_name: "闲鱼小店演示",
    platform: "xianyu",
    status: "active",
    status_label: "启用",
    has_cookie: true,
    cookie: "mock-cookie",
    session: MOCK_SESSIONS.connected,
    actions: { can_connect: false, can_disconnect: true, can_rescan: false },
  }),
  makeAccount({
    account_id: "xy:demo-shop-02",
    display_name: "二手数码号",
    platform: "xianyu",
    status: "active",
    status_label: "启用",
    has_cookie: true,
    cookie: "mock-cookie",
    session: MOCK_SESSIONS.disconnected,
    actions: { can_connect: true, can_disconnect: false, can_rescan: false },
  }),
  makeAccount({
    account_id: "1688:wholesale-01",
    display_name: "1688 批发档口",
    platform: "ali1688",
    status: "active",
    status_label: "启用",
    has_cookie: true,
    cookie: "mock-cookie",
    session: MOCK_SESSIONS.loggedIn,
    actions: { can_connect: false, can_disconnect: false, can_rescan: false },
  }),
  makeAccount({
    account_id: "xhs:creator-01",
    display_name: "小红书种草号",
    platform: "xiaohongshu",
    status: "active",
    status_label: "启用",
    has_cookie: true,
    cookie: "mock-cookie",
    session: MOCK_SESSIONS.loggedIn,
    actions: { can_connect: false, can_disconnect: false, can_rescan: false },
  }),
];

const xianyuConfig: AccountPanelConfig = {
  platform: "xianyu",
  platformName: "闲鱼",
  appName: "闲鱼",
  supportsConnection: true,
  supportsAutoConnect: true,
};

const ali1688Config: AccountPanelConfig = {
  platform: "ali1688",
  platformName: "1688",
  appName: "手机淘宝 / 1688",
  supportsConnection: false,
};

const xiaohongshuConfig: AccountPanelConfig = {
  platform: "xiaohongshu",
  platformName: "小红书",
  appName: "小红书",
  supportsConnection: false,
};

export const ACCOUNT_TABS: AccountsTab[] = [
  { id: "xianyu", label: "闲鱼账号", config: xianyuConfig },
  { id: "ali1688", label: "1688账号", config: ali1688Config },
  { id: "xiaohongshu", label: "小红书账号", config: xiaohongshuConfig },
];

export function filterAccountsByPlatform(platform: AccountPanelConfig["platform"]) {
  return MOCK_ACCOUNTS.filter((account) => account.platform === platform);
}

/** 模拟 connect IPC 成功后的账号快照。 */
export function mockAccountAfterConnect(account: AccountListItem): AccountListItem {
  const session = account.platform === "xianyu" ? MOCK_SESSIONS.connected : MOCK_SESSIONS.loggedIn;
  return {
    ...account,
    session,
    actions:
      account.platform === "xianyu"
        ? { can_connect: false, can_disconnect: true, can_rescan: false }
        : { can_connect: false, can_disconnect: false, can_rescan: false },
  };
}

/** 模拟 disconnect IPC 成功后的账号快照。 */
export function mockAccountAfterDisconnect(account: AccountListItem): AccountListItem {
  return {
    ...account,
    session: MOCK_SESSIONS.disconnected,
    actions: { can_connect: true, can_disconnect: false, can_rescan: false },
  };
}

/** 模拟 connect 进行中的账号快照。 */
export function mockAccountWhileConnecting(account: AccountListItem): AccountListItem {
  return {
    ...account,
    session: MOCK_SESSIONS.connecting,
    actions: { can_connect: false, can_disconnect: false, can_rescan: false },
  };
}

/** 从 API 记录恢复账号卡片（会话态由后端组装）。 */
export function accountFromStorage(
  platform: string,
  record: {
    account_id: string;
    display_name: string;
    avatar_url?: string | null;
    cookie: string;
    status: string;
    status_label: string;
    has_cookie: boolean;
    auto_connect?: boolean;
    session: AccountSessionView;
    actions: AccountActionsView;
  },
): AccountListItem {
  return {
    account_id: record.account_id,
    display_name: record.display_name,
    avatar_url: record.avatar_url ?? undefined,
    platform,
    status: record.status,
    status_label: record.status_label,
    has_cookie: record.has_cookie,
    cookie: record.cookie,
    session: record.session,
    actions: record.actions,
  };
}

/** 扫码登录成功后的乐观快照（随后应 reloadAccounts 以同步后端状态）。 */
export function accountFromQrLogin(
  platform: string,
  platformName: string,
  result: AccountQrCheckResponse,
  serverSession?: { session: AccountSessionView; actions: AccountActionsView },
): AccountListItem {
  const session = serverSession?.session ?? MOCK_SESSIONS.loggedIn;
  const actions = serverSession?.actions ?? {
    can_connect: platform === "xianyu",
    can_disconnect: false,
    can_rescan: false,
  };
  return {
    account_id: result.account_id ?? `${platform}:new-${Date.now()}`,
    display_name: result.display_name ?? `新${platformName}账号`,
    avatar_url: result.avatar_url ?? undefined,
    platform,
    status: "active",
    status_label: "启用",
    has_cookie: Boolean(result.cookie?.trim()),
    cookie: result.cookie ?? undefined,
    session,
    actions,
  };
}

/** 登录态探活后的账号快照。 */
export function accountFromAuthProbe(
  platform: string,
  account: AccountListItem,
  result: AccountAuthProbeResponse,
): AccountListItem {
  if (!result.valid) {
    return {
      ...account,
      session: MOCK_SESSIONS.authExpired,
      actions:
        platform === "xianyu"
          ? { can_connect: true, can_disconnect: false, can_rescan: true }
          : { can_connect: false, can_disconnect: false, can_rescan: true },
    };
  }

  const session = platform === "xianyu" ? MOCK_SESSIONS.connected : MOCK_SESSIONS.loggedIn;
  const cookie = result.cookie?.trim() || account.cookie;
  return {
    ...account,
    account_id: result.account_id ?? account.account_id,
    display_name: result.display_name ?? account.display_name,
    avatar_url: result.avatar_url ?? account.avatar_url,
    cookie,
    has_cookie: Boolean(cookie?.trim()),
    session,
    actions:
      platform === "xianyu"
        ? { can_connect: false, can_disconnect: true, can_rescan: false }
        : { can_connect: false, can_disconnect: false, can_rescan: false },
  };
}

/** @deprecated 使用 accountFromQrLogin */
export function mockAccountAfterQrLogin(platform: string, platformName: string): AccountListItem {
  return accountFromQrLogin(platform, platformName, {
    ok: true,
    status: "success",
    account_id: `${platform}:new-${Date.now()}`,
    display_name: `新${platformName}账号`,
    cookie: "mock-cookie",
  });
}
