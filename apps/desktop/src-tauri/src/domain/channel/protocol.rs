//! 渠道统一协议 — 多平台实现的扩展点。
//!
//! 新平台接入：在 `core::platform` 注册渠道，并实现 [`ChannelProtocol`]，
//! 并注册进 [`super::dispatcher::ChannelDispatcher`]。

use crate::contracts::DingDaResult;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use thiserror::Error;

/// 渠道类型。新增平台时在此扩展（与 `capabilities::builtin_descriptors` 对齐）。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ChannelKind {
    Xianyu,
    /// 1688（账号 / 登录；无闲鱼 WS 协议）。
    Ali1688,
    /// 小红书（协议实现待接入，能力层已声明）。
    Xiaohongshu,
    /// 抖音（协议实现待接入，能力层已声明）。
    Douyin,
}

impl ChannelKind {
    /// 契约中的渠道标识（小写字符串）。
    pub fn as_str(&self) -> &'static str {
        match self {
            ChannelKind::Xianyu => "xianyu",
            ChannelKind::Ali1688 => "ali1688",
            ChannelKind::Xiaohongshu => "xiaohongshu",
            ChannelKind::Douyin => "douyin",
        }
    }

    /// 从契约字符串解析渠道类型；未知类型返回 `None`。
    #[allow(clippy::should_implement_trait)]
    pub fn from_str(value: &str) -> Option<Self> {
        match value {
            "xianyu" => Some(ChannelKind::Xianyu),
            "ali1688" | "1688" => Some(ChannelKind::Ali1688),
            "xiaohongshu" => Some(ChannelKind::Xiaohongshu),
            "douyin" => Some(ChannelKind::Douyin),
            _ => None,
        }
    }

    /// 全部已知平台。
    pub fn all() -> [Self; 4] {
        [
            ChannelKind::Xianyu,
            ChannelKind::Ali1688,
            ChannelKind::Xiaohongshu,
            ChannelKind::Douyin,
        ]
    }
}

impl std::fmt::Display for ChannelKind {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(self.as_str())
    }
}

/// 连接状态枚举（与 UI 展示、`channel.event.status` 契约字符串对齐）。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConnectionState {
    Disconnected,
    Connecting,
    Connected,
    Error,
}

impl ConnectionState {
    pub fn as_str(&self) -> &'static str {
        match self {
            ConnectionState::Disconnected => "disconnected",
            ConnectionState::Connecting => "connecting",
            ConnectionState::Connected => "connected",
            ConnectionState::Error => "error",
        }
    }
}

impl std::fmt::Display for ConnectionState {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(self.as_str())
    }
}

/// 渠道协议错误。
#[derive(Debug, Error)]
pub enum ChannelError {
    #[error("channel error: {0}")]
    Protocol(String),
    #[error("not connected: {0}")]
    NotConnected(String),
    #[error("transport: {0}")]
    Transport(String),
}

/// 会话同步原语（`userConvs` 批量下发），应用层据此 upsert 会话。
#[derive(Debug, Clone)]
pub struct ConversationSync {
    pub account_id: String,
    /// goofish 会话 id（裸数字）。
    pub cid: String,
    /// 会话对端用户 id（买家 userId）。
    pub peer_id: String,
    pub item_id: String,
    pub item_title: String,
    /// 毫秒时间戳。
    pub updated_at: String,
}

/// 入站消息监听器 — 由应用层（coordinator）实现，协议层回调。
#[async_trait]
pub trait InboundListener: Send + Sync {
    async fn on_message(&self, message: ChannelInboundMessage);
    async fn on_state(&self, account_id: &str, state: ConnectionState, detail: Option<String>);

    /// 会话列表同步（`userConvs` 等批量下发）——仅更新会话，不插消息。
    async fn on_conversation(&self, _sync: ConversationSync) {}
}

/// 协议层归一化后的入站消息（`common` 下沉，`business`/`platform` 共用）。
pub use crate::contracts::channel_inbound_message::ChannelInboundMessage;

/// 单条历史消息（`MessageManager/listUserMessages` 返回，跨平台 DTO）。
///
/// 帧格式参考 goofish-cli `core/ws.py`：`um.message.extension.senderUserId`、
/// `reminderTitle`（发送者昵称）、内容 `content.custom.data`（base64 JSON 解码）。
#[derive(Debug, Clone)]
pub struct HistoryMessage {
    /// 发送者 userId。
    pub sender_user_id: String,
    /// 发送者昵称。
    pub sender_user_name: String,
    /// 正文（已解码）。
    pub content: String,
    /// 毫秒时间戳。
    pub created_at_ms: i64,
}

/// 渠道协议统一接口 — 平台各自实现。
///
/// 设计约束：
/// - 协议层不感知业务（不读库、不决策回复、不调 LLM）；
/// - 入站消息通过 [`InboundListener`] 上抛，由 Rust 协调者统一处理；
/// - `send` 返回平台侧消息 id，作为幂等键。
#[async_trait]
pub trait ChannelProtocol: Send + Sync {
    fn kind(&self) -> ChannelKind;

    /// 建立长连接并开始收消息（异步任务在内部派生）。
    async fn connect(&self, account: &ChannelAccount) -> DingDaResult<()>;

    /// 断开连接。
    async fn disconnect(&self) -> DingDaResult<()>;

    /// 向 `cid`（会话）内的 `peer_id` 发送文本，返回平台侧消息 id。
    async fn send(&self, cid: &str, peer_id: &str, text: &str) -> DingDaResult<String>;

    fn connection_state(&self) -> ConnectionState;

    /// 当前正在使用该协议实例的账号 id；单连接协议需实现。
    fn active_account_id(&self) -> Option<String> {
        None
    }

    /// 拉取某会话的完整消息历史（未实现时返回空列表）。
    async fn fetch_history(&self, _cid: &str) -> DingDaResult<Vec<HistoryMessage>> {
        Ok(Vec::new())
    }

    fn set_inbound_listener(&self, listener: Arc<dyn InboundListener>);
}

/// 渠道账号（业务层复用的契约 DTO）。
pub use crate::contracts::ChannelAccount;

/// 将 [`ChannelError`] 转为全局 [`crate::contracts::DingDaError`]（协议层边界汇总）。
impl From<ChannelError> for crate::contracts::DingDaError {
    fn from(err: ChannelError) -> Self {
        crate::contracts::DingDaError::channel(err.to_string())
    }
}
