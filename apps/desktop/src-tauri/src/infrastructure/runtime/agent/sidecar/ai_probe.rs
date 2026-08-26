//! Sidecar route binding: /v1/ai/probe_key + /v1/ai/account_balance

use serde::{Deserialize, Serialize};

use crate::infrastructure::runtime::python::client::{SidecarClient, SidecarClientError};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiProbeKeyRequest {
    pub base_url: String,
    pub api_key: String,
    #[serde(default)]
    pub kind: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiProbeKeyResponse {
    pub ok: bool,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiAccountBalanceRequest {
    pub base_url: String,
    pub api_key: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiBalanceInfo {
    pub currency: String,
    pub total_balance: String,
    pub granted_balance: String,
    pub topped_up_balance: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiAccountBalanceResponse {
    pub ok: bool,
    pub is_available: bool,
    pub balances: Vec<AiBalanceInfo>,
    pub message: String,
}

pub async fn probe_key(
    client: &SidecarClient,
    request: AiProbeKeyRequest,
) -> Result<AiProbeKeyResponse, SidecarClientError> {
    client.post_json("/v1/ai/probe_key", &request).await
}

pub async fn account_balance(
    client: &SidecarClient,
    request: AiAccountBalanceRequest,
) -> Result<AiAccountBalanceResponse, SidecarClientError> {
    client.post_json("/v1/ai/account_balance", &request).await
}
