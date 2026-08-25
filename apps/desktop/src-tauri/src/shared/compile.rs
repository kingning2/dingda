//! 编译期渠道平台选择 — re-export `crate::servers::protocol::compile`（`DINGDA_CHANNEL_PLATFORM` 相关）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

#[allow(unused_imports)]
pub use crate::servers::protocol::compile::{
    active_kind, is_active, is_active_id, ACTIVE_PLATFORM,
};
