//! 任务副驾 — Rust pipe 中转（前端不经 HTTP 直连 Python）。

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use tauri::State;

use crate::bootstrap::state::AppState;
use crate::commands::response::IpcResponse;
use crate::config::ConfigStore;
use crate::contracts::gen::ai::AiIpcConfigResponse;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CopilotRunStartRequest {
    #[serde(default)]
    pub thread_id: Option<String>,
    #[serde(default)]
    pub run_id: Option<String>,
    pub messages: Value,
    #[serde(default)]
    pub state: Option<Value>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CopilotRunStartResponse {
    pub run_id: String,
    pub thread_id: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CopilotRunAbortRequest {
    pub run_id: String,
}

#[derive(Debug, Deserialize)]
struct CopilotRunStartSidecarResponse {
    ok: bool,
    run_id: Option<String>,
    thread_id: Option<String>,
    message: Option<String>,
}

async fn resolve_ai_credentials(config: &ConfigStore) -> Option<(String, String, String)> {
    let cfg: AiIpcConfigResponse = config.ai_get().await.ok()?;
    let account = cfg.accounts.first()?;
    let provider = cfg
        .providers
        .iter()
        .find(|item| item.id == account.provider_id)?;
    let api_key = account.api_key.clone();
    let base_url = provider.base_url.clone().unwrap_or_default();
    let model = account
        .default_model
        .clone()
        .or_else(|| provider.default_model.clone())
        .unwrap_or_else(|| "qwen-plus".to_string());
    if api_key.is_empty() {
        return None;
    }
    Some((api_key, base_url, model))
}

/// sidecar 管道就绪即可启动副驾（不再暴露 HTTP 端点给前端）。
#[tauri::command]
pub async fn copilot_ready(
    state: State<'_, AppState>,
) -> crate::contracts::DingDaResult<IpcResponse<bool>> {
    let ready = state
        .lifecycle
        .client()
        .health_check()
        .await
        .unwrap_or(false);
    Ok(IpcResponse::ok(ready))
}

/// 经 pipe 启动一轮副驾对话；AG-UI 事件经 `app/copilot/agui` 推送。
#[tauri::command]
pub async fn copilot_run_start(
    state: State<'_, AppState>,
    config: State<'_, Arc<ConfigStore>>,
    request: CopilotRunStartRequest,
) -> crate::contracts::DingDaResult<IpcResponse<CopilotRunStartResponse>> {
    let (api_key, base_url, model) =
        resolve_ai_credentials(config.inner())
            .await
            .ok_or_else(|| {
                crate::contracts::DingDaError::validation("AI 账号未配置，请先在设置中添加")
            })?;

    let mut body = json!({
        "threadId": request.thread_id,
        "runId": request.run_id,
        "messages": request.messages,
        "state": request.state.unwrap_or(Value::Object(Default::default())),
        "default_api_key": api_key,
        "default_base_url": base_url,
        "default_model": model,
    });

    if body.get("threadId").and_then(Value::as_str).is_none() {
        body["threadId"] = json!(uuid::Uuid::new_v4().to_string());
    }
    if body.get("runId").and_then(Value::as_str).is_none() {
        body["runId"] = json!(uuid::Uuid::new_v4().to_string());
    }

    let response: CopilotRunStartSidecarResponse = state
        .lifecycle
        .client()
        .post_json("/v1/copilot/run_start", &body)
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

    if !response.ok {
        return Err(crate::contracts::DingDaError::wrap(
            response
                .message
                .unwrap_or_else(|| "副驾启动失败".to_string()),
        ));
    }

    let run_id = response
        .run_id
        .ok_or_else(|| crate::contracts::DingDaError::wrap("sidecar 未返回 run_id"))?;
    let thread_id = response
        .thread_id
        .or_else(|| {
            body.get("threadId")
                .and_then(Value::as_str)
                .map(str::to_string)
        })
        .ok_or_else(|| crate::contracts::DingDaError::wrap("sidecar 未返回 thread_id"))?;

    Ok(IpcResponse::ok(CopilotRunStartResponse {
        run_id,
        thread_id,
    }))
}

/// 取消指定副驾对话轮（页面卸载或新消息前调用）。
#[tauri::command]
pub async fn copilot_run_abort(
    state: State<'_, AppState>,
    request: CopilotRunAbortRequest,
) -> crate::contracts::DingDaResult<IpcResponse<()>> {
    let _: Value = state
        .lifecycle
        .client()
        .post_json(
            "/v1/copilot/run_abort",
            &json!({ "run_id": request.run_id }),
        )
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;
    Ok(IpcResponse::ok(()))
}
