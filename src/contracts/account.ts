/**
 * 账号相关契约 — 与 Python sidecar / Tauri IPC 响应对齐。
 * 前端只消费这些字段，不在组件内定义状态枚举或文案映射。
 */

export type AccountPlatform = "xianyu" | "ali1688" | "xiaohongshu";

/** channel/event/status 与登录探针聚合后的展示态（由服务端组装）。 */
export interface AccountSessionView {
  state: string;
  label: string;
  hint?: string | null;
  badge_class: string;
}

/** 账号卡片可用操作（由服务端根据 session 计算）。 */
export interface AccountActionsView {
  can_connect: boolean;
  can_disconnect: boolean;
  can_rescan: boolean;
}

/** 账号列表项（account_list 单条记录 + 会话展示）。 */
export interface AccountListItem {
  account_id: string;
  display_name: string;
  avatar_url?: string;
  platform: string;
  status: string;
  status_label: string;
  has_cookie: boolean;
  cookie?: string;
  session: AccountSessionView;
  actions: AccountActionsView;
}

/** 扫码轮询响应（contracts/schema/v1/channel/sidecar/qr_check.response）。 */
export interface AccountQrCheckResponse {
  ok: boolean;
  status: string;
  session_id?: string | null;
  detail?: string | null;
  qr_base64?: string | null;
  qr_url?: string | null;
  account_id?: string | null;
  display_name?: string | null;
  avatar_url?: string | null;
  cookie?: string | null;
}

/** 登录态探活响应 */
export interface AccountAuthProbeResponse {
  ok: boolean;
  valid: boolean;
  platform: string;
  account_id?: string | null;
  display_name?: string | null;
  avatar_url?: string | null;
  cookie?: string | null;
  detail?: string | null;
  error?: string | null;
}

/** 扫码启动响应（contracts/schema/v1/channel/sidecar/qr_start.response）。 */
export interface AccountQrStartResponse {
  ok: boolean;
  status: string;
  session_id?: string | null;
  qr_base64?: string | null;
  qr_url?: string | null;
  detail?: string | null;
}
