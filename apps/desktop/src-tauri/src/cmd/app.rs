//! 应用版本与 Runtime 生命周期状态 IPC。

use crate::contracts::DingDaResult;
use serde::Serialize;
use tauri::{AppHandle, State};

use crate::cmd::IpcResponse;
use crate::core::manager::agent::AgentState;
use crate::core::manager::python::{PythonSidecarSnapshot, PythonState};
use crate::core::manager::tasks::Task;
use crate::core::manager::RuntimeState;
use crate::utils::state::AppState;

/// 读取当前应用版本（与 `tauri.conf.json` / Cargo 版本一致）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
///
/// # 参数
///
/// * `app` — Tauri 应用句柄
///
/// # 返回值
///
/// 语义化版本字符串，如 `0.1.0`。
#[tauri::command]
pub fn app_version(app: AppHandle) -> DingDaResult<IpcResponse<String>> {
    Ok(IpcResponse::ok(app.package_info().version.to_string()))
}

/// Runtime 生命周期状态（供前端观测 / 控制）。
#[derive(Debug, Clone, Serialize)]
pub struct RuntimeStatusDto {
    /// 整个 Runtime 状态。
    pub state: RuntimeState,
    /// Python 生命周期状态。
    pub python: PythonState,
    /// Agent 生命周期状态。
    pub agent: AgentState,
    /// 全部后台任务（含状态 / 阶段 / 时间戳）。
    pub tasks: Vec<Task>,
    /// Python Sidecar 运行时快照（编排进度 / WSS / 错误）。
    #[serde(skip_serializing_if = "Option::is_none")]
    pub python_detail: Option<PythonSidecarSnapshot>,
}

/// 查询 Runtime 生命周期状态。
#[tauri::command]
pub async fn runtime_status(
    state: State<'_, AppState>,
) -> DingDaResult<IpcResponse<RuntimeStatusDto>> {
    let supervisor = &state.supervisor;
    let python_detail = supervisor
        .sync_python()
        .await
        .or_else(|| supervisor.python_snapshot());
    Ok(IpcResponse::ok(RuntimeStatusDto {
        state: supervisor.state(),
        python: supervisor.python_state(),
        agent: supervisor.agent_state(),
        tasks: supervisor.tasks().list(),
        python_detail,
    }))
}

/// 取消指定后台任务（按任务 id）。
#[tauri::command]
pub fn runtime_task_cancel(state: State<'_, AppState>, task_id: String) -> IpcResponse<()> {
    state.supervisor.tasks().cancel(&task_id);
    IpcResponse::ok(())
}
