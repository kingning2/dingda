//! Sidecar route: /v1/ws/status (POST)

use serde::{Deserialize, Serialize};
use serde_json::Value;

use super::super::client::{SidecarClient, SidecarClientError};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsStatusRequest {
    #[serde(default)]
    pub account_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WsStatusResponse {
    pub ok: bool,
    #[serde(default)]
    pub connections: Vec<Value>,
}

pub async fn call(
    client: &SidecarClient,
    request: WsStatusRequest,
) -> Result<WsStatusResponse, SidecarClientError> {
    client.post_json("/v1/ws/status", &request).await
}
