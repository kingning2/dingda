/** 账号登录态探针完成（Rust 推送后广播给各 UI 模块）。 */
export const ACCOUNTS_SESSION_PROBED_EVENT = "dingda:accounts-session-probed";

export function dispatchAccountsSessionProbed(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(ACCOUNTS_SESSION_PROBED_EVENT));
  }
}
