//! 渠道协议 seam — `ChannelProtocol` / dispatcher / 能力清单 / 编译期平台选择。

pub mod capabilities;
pub mod compile;
pub mod dispatcher;
#[allow(clippy::module_inception)]
pub mod protocol;
pub mod registry;

pub use dispatcher::ChannelDispatcher;
pub use protocol::{
    ChannelAccount, ChannelError, ChannelInboundMessage, ChannelKind, ChannelProtocol,
    ConnectionState, ConversationSync, HistoryMessage, InboundListener,
};
