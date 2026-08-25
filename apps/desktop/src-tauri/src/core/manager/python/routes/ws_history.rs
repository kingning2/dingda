//! Sidecar route: /v1/ws/history (POST)

use serde::{Deserialize, Serialize};

use super::super::client::{SidecarClient, SidecarClientError};

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

pub async fn call(
    client: &SidecarClient,
    request: WsHistoryRequest,
) -> Result<WsHistoryResponse, SidecarClientError> {
    client.post_json("/v1/ws/history", &request).await
}
