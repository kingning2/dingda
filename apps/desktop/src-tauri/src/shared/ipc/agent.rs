//! Agent IPC — LangGraph agent 对话。

use common::DingDaResult;
use serde::{Deserialize, Serialize};
use tauri::State;

use crate::shared::ipc::IpcResponse;
use crate::shared::state::AppState;

/// LangGraph agent 对话请求（provider 配置由调用方携带）。
#[derive(Debug, Deserialize)]
pub struct AgentReplyRequestDto {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
    #[serde(default)]
    pub system: Option<String>,
    pub user: String,
}

/// LangGraph agent 对话响应。
#[derive(Debug, Clone, Serialize)]
pub struct AgentReplyResult {
    pub ok: bool,
    pub reply: Option<String>,
    pub message: Option<String>,
}

/// 调用 sidecar 内的 LangGraph agent。
#[tauri::command]
pub async fn agent_reply(
    state: State<'_, AppState>,
    request: AgentReplyRequestDto,
) -> DingDaResult<IpcResponse<AgentReplyResult>> {
    let client = state.lifecycle.client().clone();
    let response = crate::runtime::python::routes::agent_reply::call(&client, request.into())
        .await
        .map_err(|error| error.to_string())?;
    Ok(IpcResponse::ok(AgentReplyResult {
        ok: response.ok,
        reply: response.reply,
        message: response.message,
    }))
}

impl From<AgentReplyRequestDto> for crate::runtime::python::routes::agent_reply::AgentReplyRequest {
    fn from(dto: AgentReplyRequestDto) -> Self {
        Self {
            base_url: dto.base_url,
            api_key: dto.api_key,
            model: dto.model,
            system: dto.system,
            user: dto.user,
        }
    }
}
