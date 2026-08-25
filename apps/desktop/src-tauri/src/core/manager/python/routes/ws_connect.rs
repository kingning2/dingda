//! Sidecar route: /v1/ws/connect (POST)

use serde::{Deserialize, Serialize};
use serde_json::Value;

use super::super::client::{SidecarClient, SidecarClientError};

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

pub async fn call(
    client: &SidecarClient,
    request: WsConnectRequest,
) -> Result<WsConnectResponse, SidecarClientError> {
    client.post_json("/v1/ws/connect", &request).await
}
