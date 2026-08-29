//! Sidecar 渠道会话 RPC — 长连接建立 / 消息收发 / 事件轮询 / 历史与批量会话。
//!
//! 路由：`/v1/ws/connect` · `disconnect` · `send` · `events/poll` ·
//! `history`、`/v1/channel/sessions_batch`（均 POST）。

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::contracts::ChannelCookie;
use crate::infrastructure::sidecar::client::{SidecarClient, SidecarClientError};

/// 建立平台长连接（`/v1/ws/connect`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsConnectRequest {
    pub account_id: String,
    pub cookies: Vec<Value>,
    #[serde(default)]
    pub auto_reply: bool,
    #[serde(default)]
    pub ai_settings: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsConnectResponse {
    pub ok: bool,
    #[serde(default)]
    pub account_id: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn ws_connect(
    client: &SidecarClient,
    request: WsConnectRequest,
) -> Result<WsConnectResponse, SidecarClientError> {
    client.post_json("/v1/ws/connect", &request).await
}

/// 断开平台长连接（`/v1/ws/disconnect`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsDisconnectRequest {
    pub account_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsDisconnectResponse {
    pub ok: bool,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn ws_disconnect(
    client: &SidecarClient,
    request: WsDisconnectRequest,
) -> Result<WsDisconnectResponse, SidecarClientError> {
    client.post_json("/v1/ws/disconnect", &request).await
}

/// 发送消息（`/v1/ws/send`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsSendRequest {
    pub account_id: String,
    pub cid: String,
    pub peer_id: String,
    pub text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsSendResponse {
    pub ok: bool,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn ws_send(
    client: &SidecarClient,
    request: WsSendRequest,
) -> Result<WsSendResponse, SidecarClientError> {
    client.post_json("/v1/ws/send", &request).await
}

/// 轮询推送事件（`/v1/ws/events/poll`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsEventsPollRequest {
    pub account_id: String,
    #[serde(default)]
    pub limit: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsEventsPollResponse {
    pub ok: bool,
    #[serde(default)]
    pub events: Vec<Value>,
}

pub async fn ws_events_poll(
    client: &SidecarClient,
    request: WsEventsPollRequest,
) -> Result<WsEventsPollResponse, SidecarClientError> {
    client.post_json("/v1/ws/events/poll", &request).await
}

/// 拉取会话历史（`/v1/ws/history`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsHistoryRequest {
    pub account_id: String,
    pub cid: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsHistoryMessage {
    pub sender_user_id: String,
    #[serde(default)]
    pub sender_user_name: String,
    pub content: String,
    #[serde(default)]
    pub created_at_ms: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsHistoryResponse {
    pub ok: bool,
    #[serde(default)]
    pub messages: Vec<WsHistoryMessage>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn ws_history(
    client: &SidecarClient,
    request: WsHistoryRequest,
) -> Result<WsHistoryResponse, SidecarClientError> {
    client.post_json("/v1/ws/history", &request).await
}

/// 批量查询会话状态（`/v1/channel/sessions_batch`）。
#[derive(Debug, Clone, Serialize)]
pub struct SessionsBatchTarget<'a> {
    pub account_id: &'a str,
    pub platform: &'a str,
    pub cookies: &'a [ChannelCookie],
}

pub async fn sessions_batch(
    client: &SidecarClient,
    targets: Vec<SessionsBatchTarget<'_>>,
    refresh: bool,
    trace_id: String,
) -> Result<Value, SidecarClientError> {
    let payload_targets: Vec<Value> = targets
        .iter()
        .map(|target| {
            json!({
                "account_id": target.account_id,
                "platform": target.platform,
                "cookies": target.cookies,
            })
        })
        .collect();
    client
        .post_json(
            "/v1/channel/sessions_batch",
            &json!({
                "targets": payload_targets,
                "refresh": refresh,
                "trace_id": trace_id,
            }),
        )
        .await
}
