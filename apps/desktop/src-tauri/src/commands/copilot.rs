//! CopilotKit 副驾 — 直连端点发现。
//!
//! 边界（CHG-20260829-007）：React 允许直连 sidecar 副驾 HTTP（AG-UI SSE，
//! 见 `contracts/schema/v1/copilot/AG_UI_MAPPING.md`）；Rust 仅做端口发现，
//! 不转发业务流量；文件 / SQLite 持久化一律由 Rust 处理，Python 经 pipe RPC 通知。

use serde::Deserialize;
use serde_json::json;
use tauri::State;

use crate::bootstrap::state::AppState;
use crate::commands::response::IpcResponse;

#[derive(Debug, Deserialize)]
struct CopilotHttpInfo {
    ok: bool,
    port: Option<u16>,
}

/// 副驾直连端点 URL；sidecar 未就绪或辅助 HTTP 未启动时 data 为 None。
#[tauri::command]
pub async fn copilot_endpoint(
    state: State<'_, AppState>,
) -> crate::contracts::DingDaResult<IpcResponse<Option<String>>> {
    let info: Result<CopilotHttpInfo, _> = state
        .lifecycle
        .client()
        .post_json("/v1/copilot/http_info", &json!({}))
        .await;

    let endpoint = match info {
        Ok(http) if http.ok => http
            .port
            .map(|port| format!("http://127.0.0.1:{port}/v1/copilot/agui")),
        _ => None,
    };
    Ok(IpcResponse::ok(endpoint))
}
