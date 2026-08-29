//! 渠道入站消息归一化 DTO。
//!
//! 协议层归一化后的入站消息（应用层继续加工为 [`crate::contracts::ChannelMessage`]）。
//! 由 `business`（channel.rs）与 `platform`（协议层）共用，故下沉到 `common`，
//! 避免 `business` 依赖 `platform`。

/// 协议层归一化后的入站消息。
#[derive(Debug, Clone)]
pub struct ChannelInboundMessage {
    pub account_id: String,
    /// 会话对端用户 id（买家 userId）。
    pub peer_id: String,
    /// 会话对端昵称。
    pub peer_name: String,
    /// 关联商品 id。
    pub item_id: String,
    /// goofish 会话 id（cid，`xxx@goofish` 的裸数字），消息历史/发送使用。
    pub cid: String,
    pub content: String,
    pub created_at_ms: i64,
}
