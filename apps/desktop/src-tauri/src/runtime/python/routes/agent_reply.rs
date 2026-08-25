//! Sidecar route binding: /v1/agent/reply (POST) — LangGraph agent 对话。

use serde::{Deserialize, Serialize};

use super::super::client::{SidecarClient, SidecarClientError};

/// LangGraph agent 对话请求（provider 配置由调用方携带）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentReplyRequest {
    /// OpenAI 兼容端点 base_url。
    pub base_url: String,
    pub api_key: String,
    pub model: String,
    /// 可选系统提示词。
    pub system: Option<String>,
    /// 用户输入。
    pub user: String,
}

/// LangGraph agent 对话响应。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentReplyResponse {
    pub ok: bool,
    pub reply: Option<String>,
    pub message: Option<String>,
}

pub async fn call(
    client: &SidecarClient,
    request: AgentReplyRequest,
) -> Result<AgentReplyResponse, SidecarClientError> {
    client.post_json("/v1/agent/reply", &request).await
}
