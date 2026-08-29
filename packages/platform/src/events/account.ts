/**
 * 账号登录态探活完成事件（Rust 启动生命周期推送）。
 */

import { listenEvent } from "./index";

/** 与 Rust `ACCOUNTS_SESSION_PROBED_TOPIC` 对齐。 */
export const ACCOUNTS_SESSION_PROBED_TOPIC = "dingda/accounts-session-probed";

export interface AccountSessionProbeItem {
  account_id: string;
  online: boolean;
}

export interface AccountsSessionProbedPayload {
  probes: AccountSessionProbeItem[];
}

/** 订阅启动/后台探活完成事件。 */
export function listenAccountsSessionProbed(
  handler: (payload: AccountsSessionProbedPayload) => void,
): Promise<() => void> {
  return listenEvent<AccountsSessionProbedPayload>(ACCOUNTS_SESSION_PROBED_TOPIC, handler);
}
