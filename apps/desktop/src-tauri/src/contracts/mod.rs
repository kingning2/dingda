//! Shared DTOs and contract types.
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

pub mod channel_inbound_message;
pub mod constants;
pub mod errors;
pub mod events;
pub mod gen;
pub mod license;

pub use constants::{douyin, xianyu, xiaohongshu, FeatureFlags};
pub use errors::{DingDaError, Result as DingDaResult};
pub use events::{emit, AppEvent, EventSink};
// 生成契约统一经此处重导出，业务代码使用 `crate::contracts::Xxx` 即可。
pub use gen::agent::*;
pub use gen::ai::*;
pub use gen::channel::*;
pub use gen::plugin::*;
pub use gen::runtime::*;
