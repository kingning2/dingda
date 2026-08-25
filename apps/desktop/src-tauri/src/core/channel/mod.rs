//! 通用渠道壳层编排 — 协调器 + 持久化 + 协议 re-export。

pub use crate::core::protocol;
pub use crate::core::protocol::dispatcher;

pub use crate::utils::channel_store::{conversation_id_for, inbound_to_message, ChannelRepo};

pub mod coordinator;
