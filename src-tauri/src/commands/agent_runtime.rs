use std::collections::HashMap;
use std::path::PathBuf;

use tauri::{AppHandle, Emitter};

use crate::agent::catalog::{list_agent_registry, list_agent_runtimes};
use crate::agent::probe::{login_agent_by_id, probe_agent_by_id, AgentRuntimeLoginResult, AgentRuntimeProbeResult};
use crate::agent::registry::AgentListResponse;
use crate::runtime::event::{AgentEvent, AgentEventEnvelope};
use crate::runtime::manager::{next_run_id, RuntimeManager};

#[derive(Debug, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LaunchAgentResponse {
    pub run_id: String,
    pub started: bool,
}

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
pub async fn launch_agent_runtime(
    app: AppHandle,
    runtime_id: String,
    prompt: String,
    cwd: Option<String>,
    model_id: Option<String>,
    session_id: Option<String>,
    reasoning: Option<String>,
    extra_allowed_dirs: Option<Vec<String>>,
    run_id: Option<String>,
) -> Result<LaunchAgentResponse, String> {
    let runtime_id = runtime_id.trim().to_string();
    if !RuntimeManager::find(&runtime_id).is_some() {
        return Err(format!("未知 Runtime：{runtime_id}"));
    }

    let cwd = match cwd {
        Some(path) if !path.trim().is_empty() => PathBuf::from(path),
        _ => std::env::current_dir().map_err(|error| format!("无法获取工作目录：{error}"))?,
    };

    let run_id = run_id
        .filter(|id| !id.trim().is_empty())
        .unwrap_or_else(next_run_id);

    let session_id = session_id
        .map(|id| id.trim().to_string())
        .filter(|id| !id.is_empty());
    let reasoning = reasoning
        .map(|id| id.trim().to_string())
        .filter(|id| !id.is_empty());
    let extra_allowed_dirs = extra_allowed_dirs
        .unwrap_or_default()
        .into_iter()
        .map(|path| path.trim().to_string())
        .filter(|path| !path.is_empty())
        .map(PathBuf::from)
        .collect::<Vec<_>>();

    let invocation = RuntimeManager::build_invocation(
        &runtime_id,
        prompt,
        cwd,
        HashMap::new(),
        model_id,
        session_id,
        reasoning,
        extra_allowed_dirs,
    )?;

    let app_handle = app.clone();
    let run_id_for_task = run_id.clone();
    let runtime_id_for_task = runtime_id;

    tauri::async_runtime::spawn(async move {
        let definition = match RuntimeManager::find(&runtime_id_for_task) {
            Some(def) => def,
            None => {
                let envelope = AgentEventEnvelope {
                    run_id: run_id_for_task.clone(),
                    event: AgentEvent::Error {
                        message: format!("未知 Runtime：{runtime_id_for_task}"),
                    },
                };
                let _ = app_handle.emit("agent-event", &envelope);
                return;
            }
        };

        if let Err(error) = RuntimeManager::launch_with_app(
            &app_handle,
            invocation,
            definition,
            run_id_for_task.clone(),
        )
        .await
        {
            let envelope = AgentEventEnvelope {
                run_id: run_id_for_task.clone(),
                event: AgentEvent::Error {
                    message: error,
                },
            };
            let _ = app_handle.emit("agent-event", &envelope);
            let envelope = AgentEventEnvelope {
                run_id: run_id_for_task,
                event: AgentEvent::RunCompleted { exit_code: -1 },
            };
            let _ = app_handle.emit("agent-event", &envelope);
        }
    });

    Ok(LaunchAgentResponse {
        run_id,
        started: true,
    })
}

#[tauri::command]
pub async fn cancel_agent_runtime(run_id: String) -> Result<(), String> {
    RuntimeManager::cancel_run(&run_id).await
}
