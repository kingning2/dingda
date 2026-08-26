//! Sidecar route binding: /v1/agent/complete (POST) — 轻量 LLM 补全（非 AI Runtime）。

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentCompleteRequest {
    #[serde(default)]
    pub provider_type: Option<String>,
    #[serde(default)]
    pub api_key: Option<String>,
    #[serde(default)]
    pub base_url: Option<String>,
    #[serde(default)]
    pub model_name: Option<String>,
    #[serde(default)]
    pub system: Option<String>,
    pub user: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentCompleteResponse {
    pub ok: bool,
    #[serde(default)]
    pub reply: Option<String>,
    #[serde(default)]
    pub message: Option<String>,
}

pub async fn call(
    client: &SidecarClient,
    request: AgentCompleteRequest,
) -> Result<AgentCompleteResponse, SidecarClientError> {
    let payload: Value = serde_json::to_value(&request).map_err(|error| {
        SidecarClientError::Transport(format!("serialize agent/complete request: {error}"))
    })?;
    client.post_json("/v1/agent/complete", &payload).await
}
