/**
 * 账号管理 IPC 封装 — 多账号 CRUD + 状态切换。
 *
 * 后端：壳层 `commands/account.rs`（InMemoryAccountStore + app::account::AccountService）。
 *
 * @author agent
 * @created 2026-08-13
 */

import { callRequest } from "./invoke";

/** 账号状态（与 Rust `AccountStatus` 对齐）。 */
export type AccountStatus = "active" | "disabled";

/** 账号所属平台。 */
export type AccountPlatform = "xianyu" | "ali1688" | "xiaohongshu";

/** 账号（与 Rust `app::account::XianyuAccount` 对齐的核心字段）。 */
export interface XianyuAccount {
  id: number;
  owner_id: number;
  /** 账号标识（全局唯一）。 */
  account_id: string;
  display_name: string;
  /** 头像 URL（连接后从闲鱼同步）。 */
  avatar_url: string;
  login_id: string;
  login_password: string;
  unb: string;
  /** 本站业务 Cookie（闲鱼账号为 goofish；1688 账号为 1688 袋）。 */
  cookie: string;
  /**
   * 1688 Cookie（兼容旧双站字段；分站登录后可为空）。
   *
   * @author Xiaoman
   * @created 2026-08-22
   */
  cookie_1688?: string;
  /**
   * 平台：`xianyu` / `ali1688`。
   *
   * @author Xiaoman
   * @created 2026-08-22
   */
  platform?: AccountPlatform | string;
  /** qr / password。 */
  login_method: string;
  status: AccountStatus;
  pause_duration_minutes: number;
}

/** 账号更新补丁（缺省字段不更新）。 */
export interface AccountUpdate {
  display_name?: string;
  avatar_url?: string;
  status?: AccountStatus;
  login_id?: string;
  login_password?: string;
  /** 更新 Cookie（扫码重登 / 风控后在真实浏览器获取的新 Cookie）。 */
  cookie?: string;
  /**
   * 更新 1688 Cookie。
   *
   * @author Xiaoman
   * @created 2026-08-22
   */
  cookie_1688?: string;
}

/** 查询账号列表。 */
export function accountList(ownerId: number): Promise<XianyuAccount[]> {
  return callRequest<XianyuAccount[]>("account_list", { ownerId }).then((response) => response.data);
}

/** 新建账号。 */
export function accountCreate(
  ownerId: number,
  account: XianyuAccount,
): Promise<XianyuAccount> {
  return callRequest<XianyuAccount>("account_create", { ownerId, account }).then(
    (response) => response.data,
  );
}

/** 更新账号（部分字段）。 */
export function accountUpdate(
  ownerId: number,
  accountId: string,
  patch: AccountUpdate,
): Promise<XianyuAccount> {
  return callRequest<XianyuAccount>("account_update", { ownerId, accountId, patch }).then(
    (response) => response.data,
  );
}

/** 切换账号启用状态。 */
export function accountSetStatus(
  ownerId: number,
  accountId: string,
  status: AccountStatus,
): Promise<void> {
  return callRequest<void>("account_set_status", {
    request: { owner_id: ownerId, account_id: accountId, status },
  }).then(() => undefined);
}

/** 删除账号。 */
export function accountDelete(ownerId: number, accountId: string): Promise<void> {
  return callRequest<void>("account_delete", {
    request: { owner_id: ownerId, account_id: accountId },
  }).then(() => undefined);
}

/** 探测账号 Cookie 是否仍在线（1688 → 浏览器；闲鱼/小红书 → HTTP 刷新 token）。 */
export function accountProbeLogin(ownerId: number, accountId: string): Promise<boolean> {
  return callRequest<boolean>("account_probe_login", {
    request: { owner_id: ownerId, account_id: accountId },
  }).then((response) => response.data);
}

// ========== 业务账号扫码登录（复用 sidecar 扫码能力，成功后自动创建/更新账号） ==========

/** 扫码启动响应（与 Rust `ChannelIpcQrStartResponse` 对齐）。 */
export interface AccountQrStartResult {
  ok: boolean;
  status: string;
  session_id: string | null;
  qr_base64: string | null;
  detail: string | null;
}

/** 扫码状态轮询响应（与 Rust `ChannelIpcQrCheckResponse` 对齐）。 */
export interface AccountQrCheckResult {
  ok: boolean;
  status: string;
  session_id: string | null;
  cookies: unknown[] | null;
  detail: string | null;
  qr_base64: string | null;
}

/** 启动业务账号扫码登录。
 *
 * @author Xiaoman
 * @created 2026-08-22
 *
 * @param name - 可选展示名
 * @param platform - `xianyu` / `ali1688`
 */
export function accountQrStart(
  name?: string,
  platform: AccountPlatform = "xianyu",
): Promise<AccountQrStartResult> {
  return callRequest<AccountQrStartResult>("account_qr_start", {
    request: { name: name ?? null, platform },
  }).then((response) => response.data);
}

/** 轮询扫码状态（成功后账号已自动创建/更新）。
 *
 * @author Xiaoman
 * @created 2026-08-22
 *
 * @param sessionId - 扫码会话 ID
 * @param platform - 须与 start 一致
 */
export function accountQrCheck(
  sessionId: string,
  platform: AccountPlatform = "xianyu",
): Promise<AccountQrCheckResult> {
  return callRequest<AccountQrCheckResult>("account_qr_check", {
    request: { session_id: sessionId, platform },
  }).then((response) => response.data);
}

/** 取消业务账号扫码登录。
 *
 * @author Xiaoman
 * @created 2026-08-22
 *
 * @param sessionId - 扫码会话 ID
 * @param platform - 须与 start 一致
 */
export function accountQrCancel(
  sessionId: string,
  platform: AccountPlatform = "xianyu",
): Promise<void> {
  return callRequest<void>("account_qr_cancel", {
    request: { session_id: sessionId, platform },
  }).then(() => undefined);
}

// ========== 业务账号渠道连接（扫码后自动连接 / 手动断开连接） ==========

/** 连接业务账号（建立渠道 websocket 设备监听）。 */
export function accountConnect(ownerId: number, accountId: string): Promise<string> {
  return callRequest<string>("account_connect", {
    request: { owner_id: ownerId, account_id: accountId },
  }).then((response) => response.data);
}

/** 断开业务账号的渠道连接。 */
export function accountDisconnect(ownerId: number, accountId: string): Promise<void> {
  return callRequest<void>("account_disconnect", {
    request: { owner_id: ownerId, account_id: accountId },
  }).then(() => undefined);
}

/** 查询业务账号的渠道连接状态（connected / connecting / disconnected / error）。 */
export function accountConnectionState(ownerId: number, accountId: string): Promise<string> {
  return callRequest<string>("account_connection_state", {
    request: { owner_id: ownerId, account_id: accountId },
  }).then((response) => response.data);
}
