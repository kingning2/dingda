//! Sidecar route: /v1/ws/disconnect (POST)

use serde::{Deserialize, Serialize};

use super::super::client::{SidecarClient, SidecarClientError};

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

pub async fn call(
    client: &SidecarClient,
    request: WsDisconnectRequest,
) -> Result<WsDisconnectResponse, SidecarClientError> {
    client.post_json("/v1/ws/disconnect", &request).await
}
