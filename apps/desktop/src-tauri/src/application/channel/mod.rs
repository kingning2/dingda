//! 渠道用例编排 — 协调器 + 协议 / 存储 re-export。

pub mod coordinator;

pub use crate::domain::channel;
pub use crate::domain::channel::dispatcher;
pub use crate::infrastructure::storage::{conversation_id_for, inbound_to_message, ChannelRepo};

pub use coordinator::ChannelCoordinator;
