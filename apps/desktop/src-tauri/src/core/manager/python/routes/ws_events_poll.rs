//! Sidecar route: /v1/ws/events/poll (POST)

use serde::{Deserialize, Serialize};
use serde_json::Value;

use super::super::client::{SidecarClient, SidecarClientError};

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

pub async fn call(
    client: &SidecarClient,
    request: WsEventsPollRequest,
) -> Result<WsEventsPollResponse, SidecarClientError> {
    client.post_json("/v1/ws/events/poll", &request).await
}
