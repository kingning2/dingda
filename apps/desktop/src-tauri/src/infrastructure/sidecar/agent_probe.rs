//! Sidecar AI 探测 RPC — API Key 校验 / 账户余额 / 平台目录 / 模型列表。
//!
//! 路由：`/v1/ai/probe_key` · `account_balance` · `providers_catalog` ·
//! `list_models`（均 POST）。

use serde::{Deserialize, Serialize};

use crate::contracts::{
    AiIpcListModelsRequest, AiIpcListModelsResponse, AiIpcProvidersCatalogResponse,
};
use crate::infrastructure::sidecar::client::{SidecarClient, SidecarClientError};

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

/// 校验 API Key（`/v1/ai/probe_key`）。
pub async fn probe_key(
    client: &SidecarClient,
    request: AiProbeKeyRequest,
) -> Result<AiProbeKeyResponse, SidecarClientError> {
    client.post_json("/v1/ai/probe_key", &request).await
}

/// 查询账户余额（`/v1/ai/account_balance`）。
pub async fn account_balance(
    client: &SidecarClient,
    request: AiAccountBalanceRequest,
) -> Result<AiAccountBalanceResponse, SidecarClientError> {
    client.post_json("/v1/ai/account_balance", &request).await
}

/// 拉取 Python 已注册的 AI 平台目录（`/v1/ai/providers_catalog`）。
pub async fn providers_catalog(
    client: &SidecarClient,
) -> Result<AiIpcProvidersCatalogResponse, SidecarClientError> {
    client
        .post_json("/v1/ai/providers_catalog", &serde_json::json!({}))
        .await
}

/// 拉取平台可用模型列表（OpenAI 兼容 /models，`/v1/ai/list_models`）。
pub async fn list_models(
    client: &SidecarClient,
    request: AiIpcListModelsRequest,
) -> Result<AiIpcListModelsResponse, SidecarClientError> {
    client.post_json("/v1/ai/list_models", &request).await
}
