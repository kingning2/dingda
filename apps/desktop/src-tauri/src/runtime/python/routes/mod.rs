//! Rust ↔ Python sidecar 业务路由绑定（从 `crates/infra` 迁入）。
//!
//! 只做传输适配（`post_json` / `get_json`），不含业务逻辑；
//! 具体请求 / 响应契约来自 `common::contracts`。

pub mod agent_ping;
pub mod agent_reply;
pub mod channel_cookie_renew;
pub mod channel_login_probe;
pub mod channel_qr_cancel;
pub mod channel_qr_check;
pub mod channel_qr_start;
pub mod channel_search;
