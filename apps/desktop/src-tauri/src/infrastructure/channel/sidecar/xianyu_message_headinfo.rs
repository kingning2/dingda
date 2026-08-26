//! Sidecar: POST /v1/channel/xianyu/message_headinfo

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageHeadinfoRequest {
    pub cookie: String,
    pub session_id: String,
    #[serde(default)]
    pub item_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MessageHeadinfoResponse {
    pub ok: bool,
    #[serde(default)]
    pub data: Option<Value>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn call(
    client: &SidecarClient,
    request: MessageHeadinfoRequest,
) -> Result<MessageHeadinfoResponse, SidecarClientError> {
    client
        .post_json("/v1/channel/xianyu/message_headinfo", &request)
        .await
}
