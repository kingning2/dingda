//! 渠道协调器 — 入站处理 + 事件推送。
//!
//! 风控判定与 Cookie 续期在 Python Sidecar；本协调器只消费状态 / 消息事件。

use crate::contracts::events::{
    emit, AppEvent, ChannelMessageEvent, ChannelStatusEvent, EventSink,
};
use crate::contracts::DingDaResult;
use crate::contracts::{ChannelConversation, ChannelMessage};
use crate::domain::channel::{
    ChannelDispatcher, ChannelInboundMessage, ConnectionState, ConversationSync, InboundListener,
};
use crate::infrastructure::channel::wss_bridge::PythonWssBridge;
use crate::infrastructure::database::{conversation_id_for, inbound_to_message, ChannelRepo};
use async_trait::async_trait;

use std::sync::Arc;
use std::sync::RwLock;
use std::time::{SystemTime, UNIX_EPOCH};

fn is_auth_expired_text(text: &str) -> bool {
    [
        "FAIL_SYS_SESSION_EXPIRED",
        "Session过期",
        "SESSION_EXPIRED",
        "登录态已过期",
        "请重新扫码登录",
        "cookie 缺少",
    ]
    .iter()
    .any(|keyword| text.contains(keyword))
}

fn sanitize_status_detail(text: &str) -> String {
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return "连接异常，请稍后重试".into();
    }
    if trimmed.contains("_____tmd_____")
        || trimmed.contains("FAIL_SYS_USER_VALIDATE")
        || trimmed.contains("punish")
    {
        return "风控拦截，请稍后重试".into();
    }
    if trimmed.starts_with('{') || trimmed.len() > 120 {
        return "连接异常，请稍后重试或查看运行日志".into();
    }
    trimmed.chars().take(120).collect()
}

/// 协调器 — 持有 store / dispatcher / 事件总线。
pub struct ChannelCoordinator {
    store: Arc<ChannelRepo>,
    dispatcher: Arc<ChannelDispatcher>,
    sink: Arc<dyn EventSink>,
    wss_bridge: RwLock<Option<Arc<PythonWssBridge>>>,
}

impl ChannelCoordinator {
    pub fn new(
        store: Arc<ChannelRepo>,
        dispatcher: Arc<ChannelDispatcher>,
        sink: Arc<dyn EventSink>,
    ) -> Self {
        Self {
            store,
            dispatcher,
            sink,
            wss_bridge: RwLock::new(None),
        }
    }

    pub fn set_wss_bridge(&self, bridge: Arc<PythonWssBridge>) {
        *self
            .wss_bridge
            .write()
            .unwrap_or_else(|poisoned| poisoned.into_inner()) = Some(bridge);
    }

    /// 推送前端渠道 UI 状态（含 `renewing` / `queued`）。
    pub fn emit_ui_status(&self, account_id: &str, state: &str, detail: Option<String>) {
        self.emit_channel_status(account_id, state, detail);
    }

    fn now_iso(&self) -> String {
        let millis = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis())
            .unwrap_or(0);
        format!("{millis}")
    }

    /// 人工发送：经 WSS 桥或调度器发出，并持久化出站消息。
    pub async fn send_message(
        &self,
        conversation: &ChannelConversation,
        content: &str,
    ) -> DingDaResult<String> {
        let cid = conversation
            .cid
            .clone()
            .unwrap_or_else(|| conversation.peer_id.clone());
        let peer_id = conversation.peer_id.clone();

        let message_id = {
            let bridge = self
                .wss_bridge
                .read()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .clone();
            if let Some(bridge) = bridge {
                if bridge.is_active(&conversation.account_id).await {
                    bridge
                        .send(&conversation.account_id, &cid, &peer_id, content)
                        .await?
                } else {
                    self.dispatcher
                        .send(&conversation.account_id, &cid, &peer_id, content)
                        .await
                        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?
                }
            } else {
                self.dispatcher
                    .send(&conversation.account_id, &cid, &peer_id, content)
                    .await
                    .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?
            }
        };

        let outbound = ChannelMessage {
            id: format!("{message_id}-out"),
            conversation_id: conversation.id.clone(),
            direction: "out".to_string(),
            sender: "human".to_string(),
            content: content.to_string(),
            created_at: self.now_iso(),
        };
        self.store
            .insert_message(&outbound)
            .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;
        self.emit_channel_message(&conversation.account_id, outbound, None);
        Ok(message_id)
    }

    /// 持久化 auto_reply 出站消息。
    pub async fn record_outbound(
        &self,
        account_id: &str,
        cid: &str,
        peer_id: &str,
        item_id: &str,
        content: &str,
        message_id: &str,
    ) -> DingDaResult<()> {
        let conversation_id = if !cid.is_empty() {
            match self.store.find_conversation_by_cid(cid) {
                Ok(Some(existing)) => existing.id,
                _ => conversation_id_for(peer_id, item_id),
            }
        } else {
            conversation_id_for(peer_id, item_id)
        };
        let now = self.now_iso();
        let conversation = ChannelConversation {
            id: conversation_id.clone(),
            account_id: account_id.to_string(),
            cid: if cid.is_empty() {
                None
            } else {
                Some(cid.to_string())
            },
            peer_id: peer_id.to_string(),
            peer_name: None,
            item_id: if item_id.is_empty() {
                None
            } else {
                Some(item_id.to_string())
            },
            item_title: None,
            item_price: None,
            updated_at: now.clone(),
        };
        let _ = self.store.upsert_conversation(&conversation);
        let message = ChannelMessage {
            id: message_id.to_string(),
            conversation_id,
            direction: "out".to_string(),
            sender: "ai".to_string(),
            content: content.to_string(),
            created_at: now,
        };
        self.store
            .insert_message(&message)
            .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;
        self.emit_channel_message(account_id, message, None);
        Ok(())
    }

    fn emit_channel_status(&self, account_id: &str, state: &str, detail: Option<String>) {
        let event = AppEvent::ChannelStatus(ChannelStatusEvent {
            account_id: account_id.to_string(),
            state: state.to_string(),
            detail,
        });
        if let Err(error) = emit(self.sink.as_ref(), &event) {
            warn!(%error, account = %account_id, "推送渠道状态失败");
        }
    }

    fn emit_channel_message(
        &self,
        account_id: &str,
        message: ChannelMessage,
        suggestion: Option<String>,
    ) {
        let event = AppEvent::ChannelMessage(ChannelMessageEvent {
            account_id: account_id.to_string(),
            message,
            suggestion,
        });
        if let Err(error) = emit(self.sink.as_ref(), &event) {
            warn!(%error, "推送渠道消息失败");
        }
    }
}

#[async_trait]
impl InboundListener for ChannelCoordinator {
    async fn on_message(&self, inbound: ChannelInboundMessage) {
        let conversation_id = if !inbound.cid.is_empty() {
            match self.store.find_conversation_by_cid(&inbound.cid) {
                Ok(Some(existing)) => existing.id,
                Ok(None) => conversation_id_for(&inbound.peer_id, &inbound.item_id),
                Err(error) => {
                    warn!(%error, "按 cid 查会话失败");
                    conversation_id_for(&inbound.peer_id, &inbound.item_id)
                }
            }
        } else {
            conversation_id_for(&inbound.peer_id, &inbound.item_id)
        };
        let now = self.now_iso();
        let message_created_at = if inbound.created_at_ms > 0 {
            inbound.created_at_ms.to_string()
        } else {
            now.clone()
        };
        let conversation = ChannelConversation {
            id: conversation_id.clone(),
            account_id: inbound.account_id.clone(),
            cid: if inbound.cid.is_empty() {
                None
            } else {
                Some(inbound.cid.clone())
            },
            peer_id: inbound.peer_id.clone(),
            peer_name: Some(inbound.peer_name.clone()),
            item_id: Some(inbound.item_id.clone()),
            item_title: None,
            item_price: None,
            updated_at: message_created_at.clone(),
        };
        if let Err(error) = self.store.upsert_conversation(&conversation) {
            warn!(%error, "更新会话失败");
        }

        let message = inbound_to_message(&inbound, &conversation_id, &message_created_at);
        let existing = self
            .store
            .list_messages(&conversation_id)
            .unwrap_or_default();
        if existing.iter().any(|item| item.id == message.id) {
            return;
        }
        if let Err(error) = self.store.insert_message(&message) {
            warn!(%error, "写入入站消息失败");
        }
        self.emit_channel_message(&inbound.account_id, message, None);
    }

    async fn on_state(&self, account_id: &str, state: ConnectionState, detail: Option<String>) {
        match state {
            ConnectionState::Connected => {
                self.emit_channel_status(account_id, "connected", None);
            }
            ConnectionState::Disconnected => {
                self.emit_channel_status(account_id, "disconnected", None);
            }
            ConnectionState::Connecting => {
                self.emit_channel_status(account_id, "connecting", Some("正在连接闲鱼…".into()));
            }
            ConnectionState::Error => {
                let detail_text = detail.as_deref().unwrap_or("");
                if is_auth_expired_text(detail_text) {
                    self.emit_channel_status(
                        account_id,
                        "auth_expired",
                        Some("登录态已过期，请重新扫码后再连接".into()),
                    );
                    return;
                }
                self.emit_channel_status(
                    account_id,
                    "error",
                    Some(sanitize_status_detail(detail_text)),
                );
            }
        }
    }

    async fn on_conversation(&self, sync: ConversationSync) {
        let conversation_id = if !sync.cid.is_empty() {
            match self.store.find_conversation_by_cid(&sync.cid) {
                Ok(Some(existing)) => existing.id,
                Ok(None) => conversation_id_for(&sync.peer_id, &sync.item_id),
                Err(error) => {
                    warn!(%error, "按 cid 查会话失败");
                    conversation_id_for(&sync.peer_id, &sync.item_id)
                }
            }
        } else {
            conversation_id_for(&sync.peer_id, &sync.item_id)
        };

        let existing = self
            .store
            .find_conversation_by_id(&conversation_id)
            .ok()
            .flatten();
        let peer_id = match &existing {
            Some(row) if row.peer_id != sync.cid && sync.peer_id == sync.cid => row.peer_id.clone(),
            _ => sync.peer_id.clone(),
        };
        let peer_name = existing.as_ref().and_then(|row| row.peer_name.clone());
        let item_id = if sync.item_id.is_empty() {
            existing.as_ref().and_then(|row| row.item_id.clone())
        } else {
            Some(sync.item_id.clone())
        };
        let item_title = if sync.item_title.is_empty() {
            existing.as_ref().and_then(|row| row.item_title.clone())
        } else {
            Some(sync.item_title.clone())
        };

        let conversation = ChannelConversation {
            id: conversation_id,
            account_id: sync.account_id.clone(),
            cid: if sync.cid.is_empty() {
                None
            } else {
                Some(sync.cid.clone())
            },
            peer_id,
            peer_name,
            item_id,
            item_title,
            item_price: existing.as_ref().and_then(|row| row.item_price),
            updated_at: sync.updated_at,
        };
        if let Err(error) = self.store.upsert_conversation(&conversation) {
            warn!(%error, "同步会话失败");
        }
    }
}
