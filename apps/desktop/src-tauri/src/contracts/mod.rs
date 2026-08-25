//! Shared DTOs and contract types.
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

pub mod channel_inbound_message;
pub mod constants;
pub mod contracts;
pub mod errors;
pub mod events;
pub mod license;

pub use constants::{douyin, xianyu, xiaohongshu, FeatureFlags};
pub use errors::{DingDaError, Result as DingDaResult};
pub use events::{emit, AppEvent, EventSink};
