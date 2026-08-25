//! Sidecar route: /v1/ws/send (POST)

use serde::{Deserialize, Serialize};

use super::super::client::{SidecarClient, SidecarClientError};

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

pub async fn call(
    client: &SidecarClient,
    request: WsSendRequest,
) -> Result<WsSendResponse, SidecarClientError> {
    client.post_json("/v1/ws/send", &request).await
}
