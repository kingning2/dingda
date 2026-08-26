//! AI / Agent 相关 IPC。

pub use agent::{
    agent_reply, agent_run_cancel, agent_run_get, agent_run_list, agent_run_pause,
    agent_run_resume, agent_run_start, agent_run_status,
};
pub use ai::{ai_account_balance, ai_config_get, ai_config_set, ai_test_api_key};

mod agent {
    use crate::contracts::DingDaResult;
    use crate::infrastructure::runtime::agent::AgentRunRecord;
    use serde::{Deserialize, Serialize};
    use tauri::State;

    use crate::app::state::AppState;
    use crate::commands::IpcResponse;

    #[derive(Debug, Deserialize)]
    #[serde(rename_all = "camelCase")]
    pub struct AgentReplyRequestDto {
        pub base_url: String,
        pub api_key: String,
        pub model: String,
        #[serde(default)]
        pub system: Option<String>,
        pub user: String,
    }

    #[derive(Debug, Clone, Serialize)]
    #[serde(rename_all = "camelCase")]
    pub struct AgentReplyResult {
        pub ok: bool,
        pub reply: Option<String>,
        pub message: Option<String>,
        pub run_id: Option<String>,
    }

    #[derive(Debug, Deserialize)]
    #[serde(rename_all = "camelCase")]
    pub struct AgentRunStartDto {
        pub user: String,
        #[serde(default)]
        pub system: Option<String>,
        #[serde(default)]
        pub resume_from_run_id: Option<String>,
        #[serde(default)]
        pub resume_node: Option<String>,
    }

    #[derive(Debug, Deserialize)]
    #[serde(rename_all = "camelCase")]
    pub struct AgentRunIdDto {
        #[serde(default)]
        pub run_id: Option<String>,
    }

    #[derive(Debug, Deserialize)]
    #[serde(rename_all = "camelCase")]
    pub struct AgentRunResumeDto {
        #[serde(default)]
        pub run_id: Option<String>,
        /// continue | restart | seek
        pub mode: String,
        #[serde(default)]
        pub node: Option<String>,
    }

    /// 兼容旧 IPC：经 AgentRuntime start_run 并等待终态（最多 10 分钟）。
    #[tauri::command]
    pub async fn agent_reply(
        state: State<'_, AppState>,
        request: AgentReplyRequestDto,
    ) -> DingDaResult<IpcResponse<AgentReplyResult>> {
        let agent = state.supervisor.agent().clone();
        let record = agent
            .start_run_tracked(request.user, request.system, None, None)
            .await
            .map_err(|e| e.to_string())?;
        let run_id = record.id.clone();
        for _ in 0..600 {
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
            if let Some(r) = agent.list_runs().into_iter().find(|r| r.id == run_id) {
                match r.state.as_str() {
                    "completed" => {
                        return Ok(IpcResponse::ok(AgentReplyResult {
                            ok: true,
                            reply: r.reply,
                            message: None,
                            run_id: Some(run_id),
                        }));
                    }
                    "failed" | "cancelled" | "interrupted" => {
                        return Ok(IpcResponse::ok(AgentReplyResult {
                            ok: false,
                            reply: None,
                            message: r.error.or(Some(r.state)),
                            run_id: Some(run_id),
                        }));
                    }
                    _ => {}
                }
            }
        }
        Ok(IpcResponse::ok(AgentReplyResult {
            ok: false,
            reply: None,
            message: Some("timeout waiting for agent run".to_string()),
            run_id: Some(run_id),
        }))
    }

    #[tauri::command]
    pub async fn agent_run_start(
        state: State<'_, AppState>,
        request: AgentRunStartDto,
    ) -> DingDaResult<IpcResponse<AgentRunRecord>> {
        let agent = state.supervisor.agent().clone();
        let record = agent
            .start_run_tracked(
                request.user,
                request.system,
                request.resume_from_run_id,
                request.resume_node,
            )
            .await
            .map_err(|e| e.to_string())?;
        Ok(IpcResponse::ok(record))
    }

    #[tauri::command]
    pub async fn agent_run_pause(
        state: State<'_, AppState>,
        request: AgentRunIdDto,
    ) -> DingDaResult<IpcResponse<AgentRunRecord>> {
        let record = state
            .supervisor
            .agent()
            .pause_run(request.run_id)
            .await
            .map_err(|e| e.to_string())?;
        Ok(IpcResponse::ok(record))
    }

    #[tauri::command]
    pub async fn agent_run_resume(
        state: State<'_, AppState>,
        request: AgentRunResumeDto,
    ) -> DingDaResult<IpcResponse<AgentRunRecord>> {
        let record = state
            .supervisor
            .agent()
            .resume_run(request.run_id, &request.mode, request.node, None)
            .await
            .map_err(|e| e.to_string())?;
        Ok(IpcResponse::ok(record))
    }

    #[tauri::command]
    pub async fn agent_run_cancel(
        state: State<'_, AppState>,
        request: AgentRunIdDto,
    ) -> DingDaResult<IpcResponse<AgentRunRecord>> {
        let record = state
            .supervisor
            .agent()
            .cancel_run(request.run_id)
            .await
            .map_err(|e| e.to_string())?;
        Ok(IpcResponse::ok(record))
    }

    #[tauri::command]
    pub async fn agent_run_status(
        state: State<'_, AppState>,
        request: AgentRunIdDto,
    ) -> DingDaResult<IpcResponse<AgentRunRecord>> {
        let record = state
            .supervisor
            .agent()
            .run_status(request.run_id)
            .await
            .map_err(|e| e.to_string())?;
        Ok(IpcResponse::ok(record))
    }

    #[tauri::command]
    pub async fn agent_run_get(
        state: State<'_, AppState>,
        request: AgentRunIdDto,
    ) -> DingDaResult<IpcResponse<AgentRunRecord>> {
        agent_run_status(state, request).await
    }

    #[tauri::command]
    pub async fn agent_run_list(
        state: State<'_, AppState>,
    ) -> DingDaResult<IpcResponse<Vec<AgentRunRecord>>> {
        Ok(IpcResponse::ok(state.supervisor.agent().list_runs()))
    }
}

#[allow(clippy::module_inception)]
mod ai {
    // AI 配置本地落盘；Key/余额探测转发 Python sidecar。

    use crate::contracts::contracts::{AiIpcConfigRequest, AiIpcConfigResponse};
    use crate::contracts::DingDaResult;
    use serde::{Deserialize, Serialize};
    use std::sync::Arc;
    use tauri::State;

    use crate::app::state::AppState;
    use crate::commands::IpcResponse;
    use crate::config::ConfigStore;
    use crate::infrastructure::runtime::agent::sidecar::ai_probe::{
        self, AiAccountBalanceRequest, AiProbeKeyRequest,
    };

    #[derive(Debug, Clone, Serialize, Deserialize)]
    pub struct AiBalanceInfoDto {
        pub currency: String,
        pub total_balance: String,
        pub granted_balance: String,
        pub topped_up_balance: String,
    }

    #[derive(Debug, Clone, Serialize, Deserialize)]
    pub struct AiApiKeyTestResult {
        pub ok: bool,
        pub message: String,
    }

    #[derive(Debug, Clone, Serialize, Deserialize)]
    pub struct AiAccountBalanceResult {
        pub ok: bool,
        pub is_available: bool,
        pub balances: Vec<AiBalanceInfoDto>,
        pub message: String,
    }

    #[tauri::command]
    pub async fn ai_config_get(
        state: tauri::State<'_, Arc<ConfigStore>>,
    ) -> DingDaResult<IpcResponse<AiIpcConfigResponse>> {
        let result = state.ai_get().await?;
        Ok(IpcResponse::ok(result))
    }

    #[tauri::command]
    pub async fn ai_config_set(
        state: tauri::State<'_, Arc<ConfigStore>>,
        config: AiIpcConfigRequest,
    ) -> DingDaResult<IpcResponse<AiIpcConfigResponse>> {
        let result = state.ai_set(config).await?;
        Ok(IpcResponse::ok(result))
    }

    /// 探测 API Key（Python：`/v1/ai/probe_key`）。
    #[tauri::command]
    pub async fn ai_test_api_key(
        state: State<'_, AppState>,
        base_url: String,
        api_key: String,
        kind: Option<String>,
    ) -> DingDaResult<IpcResponse<AiApiKeyTestResult>> {
        let response = ai_probe::probe_key(
            state.lifecycle.client(),
            AiProbeKeyRequest {
                base_url,
                api_key,
                kind,
            },
        )
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;
        Ok(IpcResponse::ok(AiApiKeyTestResult {
            ok: response.ok,
            message: response.message,
        }))
    }

    /// 查询账号余额（Python：`/v1/ai/account_balance`）。
    #[tauri::command]
    pub async fn ai_account_balance(
        state: State<'_, AppState>,
        base_url: String,
        api_key: String,
    ) -> DingDaResult<IpcResponse<AiAccountBalanceResult>> {
        let response = ai_probe::account_balance(
            state.lifecycle.client(),
            AiAccountBalanceRequest { base_url, api_key },
        )
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;
        Ok(IpcResponse::ok(AiAccountBalanceResult {
            ok: response.ok,
            is_available: response.is_available,
            balances: response
                .balances
                .into_iter()
                .map(|b| AiBalanceInfoDto {
                    currency: b.currency,
                    total_balance: b.total_balance,
                    granted_balance: b.granted_balance,
                    topped_up_balance: b.topped_up_balance,
                })
                .collect(),
            message: response.message,
        }))
    }
}
