//! 渠道 Sidecar 路径绑定 — 经 [`SidecarClient`] 走 SHM 载荷。

pub mod channel_cookie_renew;
pub mod channel_login_probe;
pub mod channel_qr_cancel;
pub mod channel_qr_check;
pub mod channel_qr_start;
pub mod ws_connect;
pub mod ws_disconnect;
pub mod ws_events_poll;
pub mod ws_history;
pub mod ws_send;
pub mod xianyu_item_detail;
pub mod xianyu_message_headinfo;
pub mod xianyu_seller_items;
pub mod xianyu_user_profile;
