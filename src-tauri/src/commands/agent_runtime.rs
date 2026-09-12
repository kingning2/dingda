//! Agent Runtime Tauri commands：目录探测 / 登录 / 下载。
//!
//! CLI 启动与取消在 Python：`/v1/agent/runtimes/...`。

use tauri::AppHandle;

use crate::agent::catalog::{list_agent_registry, list_agent_runtimes};
use crate::agent::probe::{
    login_agent_by_id, probe_agent_by_id, AgentRuntimeLoginResult, AgentRuntimeProbeResult,
};
use crate::agent::registry::AgentListResponse;
use crate::runtime::find_runtime;
use crate::runtime::install::ManagedDownloadResult;

#[tauri::command]
pub async fn list_agent_runtimes_command(_app: AppHandle) -> Result<AgentListResponse, String> {
    Ok(list_agent_runtimes())
}

/// 仅返回注册表占位（不扫 PATH），供首次未扫描时展示「未安装」。
#[tauri::command]
pub async fn list_agent_registry_command(_app: AppHandle) -> Result<AgentListResponse, String> {
    Ok(list_agent_registry())
}

#[tauri::command]
pub async fn probe_agent_runtime(agent_id: String) -> Result<AgentRuntimeProbeResult, String> {
    probe_agent_by_id(&agent_id).await
}

#[tauri::command]
pub async fn login_agent_runtime(agent_id: String) -> Result<AgentRuntimeLoginResult, String> {
    login_agent_by_id(&agent_id).await
}

#[tauri::command]
pub async fn download_agent_runtime(agent_id: String) -> Result<ManagedDownloadResult, String> {
    let agent_id = agent_id.trim().to_string();
    let definition = find_runtime(&agent_id).ok_or_else(|| format!("未知 Runtime：{agent_id}"))?;
    definition.download_managed().await
}
