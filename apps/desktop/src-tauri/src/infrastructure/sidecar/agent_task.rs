//! Sidecar Agent 任务 RPC — graph run 启停控制 / 对话 / 轻量补全 / ping。
//!
//! 路由：`/v1/agent/run/*` · `/v1/agent/reply` · `/v1/agent/complete` ·
//! `/v1/agent/ping`（均 POST）。

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::contracts::{
    AgentSidecarPingRequest, AgentSidecarPingResponse, AgentSidecarRunCancelRequest,
    AgentSidecarRunCancelResponse, AgentSidecarRunControlRequest, AgentSidecarRunControlResponse,
    AgentSidecarRunStartRequest, AgentSidecarRunStartResponse, AgentSidecarRunStatusRequest,
    AgentSidecarRunStatusResponse, ChannelCookie,
};
use crate::domain::account::{AccountStatus, AccountStore, XianyuAccount};
use crate::infrastructure::database::cookies::{my_id, parse_credential};
use crate::infrastructure::sidecar::client::{SidecarClient, SidecarClientError};

/// 桌面默认 owner（与前端 OWNER_ID 一致）。
pub const DEFAULT_OWNER_ID: i64 = 1;

/// 选取第一个可用闲鱼账号及其 cookies，供 crawl 使用。
pub fn resolve_crawl_channel(
    store: &dyn AccountStore,
    owner_id: i64,
) -> Option<(String, Vec<ChannelCookie>)> {
    let accounts = store.list_accounts(owner_id).ok()?;
    pick_crawl_account(&accounts)
}

fn pick_crawl_account(accounts: &[XianyuAccount]) -> Option<(String, Vec<ChannelCookie>)> {
    for account in accounts {
        if account.status != AccountStatus::Active {
            continue;
        }
        if account.cookie.trim().is_empty() {
            continue;
        }
        let cookies = parse_credential(&account.cookie);
        if cookies.is_empty() || my_id(&cookies).is_none() {
            continue;
        }
        return Some((account.account_id.clone(), cookies));
    }
    None
}

/// 启动 graph run（`/v1/agent/run/start`）。
pub async fn run_start(
    client: &SidecarClient,
    request: &AgentSidecarRunStartRequest,
) -> Result<AgentSidecarRunStartResponse, SidecarClientError> {
    client.post_json("/v1/agent/run/start", request).await
}

/// 控制 graph run（暂停 / 恢复等，`/v1/agent/run/control`）。
pub async fn run_control(
    client: &SidecarClient,
    request: &AgentSidecarRunControlRequest,
) -> Result<AgentSidecarRunControlResponse, SidecarClientError> {
    client.post_json("/v1/agent/run/control", request).await
}

/// 查询 graph run 状态（`/v1/agent/run/status`）。
pub async fn run_status(
    client: &SidecarClient,
    request: &AgentSidecarRunStatusRequest,
) -> Result<AgentSidecarRunStatusResponse, SidecarClientError> {
    client.post_json("/v1/agent/run/status", request).await
}

/// 取消 graph run（`/v1/agent/run/cancel`）。
pub async fn run_cancel(
    client: &SidecarClient,
    request: &AgentSidecarRunCancelRequest,
) -> Result<AgentSidecarRunCancelResponse, SidecarClientError> {
    client.post_json("/v1/agent/run/cancel", request).await
}

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

/// Agent 对话（`/v1/agent/reply`）。
pub async fn reply(
    client: &SidecarClient,
    request: AgentReplyRequest,
) -> Result<AgentReplyResponse, SidecarClientError> {
    client.post_json("/v1/agent/reply", &request).await
}

/// 轻量 LLM 补全请求（非 AI Runtime）。
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

/// 轻量 LLM 补全（`/v1/agent/complete`）。
pub async fn complete(
    client: &SidecarClient,
    request: AgentCompleteRequest,
) -> Result<AgentCompleteResponse, SidecarClientError> {
    let payload: Value = serde_json::to_value(&request).map_err(|error| {
        SidecarClientError::Transport(format!("serialize agent/complete request: {error}"))
    })?;
    client.post_json("/v1/agent/complete", &payload).await
}

/// Agent 心跳（`/v1/agent/ping`）。
pub async fn ping(
    client: &SidecarClient,
    request: AgentSidecarPingRequest,
) -> Result<AgentSidecarPingResponse, SidecarClientError> {
    client.post_json("/v1/agent/ping", &request).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pick_skips_disabled_and_empty_cookie() {
        let accounts = vec![
            XianyuAccount {
                account_id: "a1".into(),
                status: AccountStatus::Disabled,
                cookie: "unb=U-1".into(),
                ..Default::default()
            },
            XianyuAccount {
                account_id: "a2".into(),
                status: AccountStatus::Active,
                cookie: "".into(),
                ..Default::default()
            },
        ];
        assert!(pick_crawl_account(&accounts).is_none());
    }
}
