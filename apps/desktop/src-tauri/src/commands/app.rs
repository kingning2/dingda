//! 应用系统级 IPC — 版本 / Runtime 状态 / 任务取消 / 日志 / 平台描述。

use crate::bootstrap::logging::{clear_logs, recent_logs, LogEntry};
use crate::bootstrap::state::AppState;
use crate::bootstrap::window::on_route_change;
use crate::commands::IpcResponse;
use crate::contracts::DingDaResult;
use crate::core::supervisor::RuntimeState;
use crate::domain::channel::registry::PlatformRegistry;
use crate::infrastructure::runtime::tasks::Task;
use crate::infrastructure::sidecar::AgentState;
use crate::infrastructure::sidecar::{PythonSidecarSnapshot, PythonState};
use chrono::Local;
use serde::Serialize;
use std::fs::{self, OpenOptions};
use std::io::Write;
use tauri::{AppHandle, Manager, State};

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

/// 平台描述 IPC 返回体，字段与前端约定对齐。
#[derive(Debug, Clone, Serialize)]
pub struct PlatformDescriptorDto {
    pub kind: String,
    pub name: String,
    pub capabilities: Vec<String>,
}

/// 列出当前构建已编译进二进制的平台描述。
#[tauri::command]
pub fn platform_descriptors() -> DingDaResult<IpcResponse<Vec<PlatformDescriptorDto>>> {
    let registry = PlatformRegistry::new();
    let descriptors = registry
        .descriptors()
        .into_iter()
        .map(|descriptor| PlatformDescriptorDto {
            kind: descriptor.kind,
            name: descriptor.name,
            capabilities: descriptor.capabilities.as_strings(),
        })
        .collect();
    Ok(IpcResponse::ok(descriptors))
}

const FRONTEND_LOG_TARGET: &str = "dingda.lifecycle";
const FRONTEND_LOG_FILE_NAME: &str = "frontend.log";

fn append_frontend_log_file(app: &AppHandle, level: &str, message: &str) -> std::io::Result<()> {
    let log_dir = app
        .path()
        .app_local_data_dir()
        .map_err(|error| std::io::Error::other(error.to_string()))?
        .join("logs");
    fs::create_dir_all(&log_dir)?;
    let log_file = log_dir.join(FRONTEND_LOG_FILE_NAME);
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_file)?;
    let timestamp = Local::now().format("%Y-%m-%d %H:%M:%S");
    writeln!(
        file,
        "{timestamp} {level} react {FRONTEND_LOG_TARGET} {message}"
    )
}

/// 读取最近日志（时间正序，旧 → 新）。
#[tauri::command]
pub fn log_recent(limit: Option<usize>) -> IpcResponse<Vec<LogEntry>> {
    IpcResponse::ok(recent_logs(limit.unwrap_or(500)))
}

/// 清空日志缓冲。
#[tauri::command]
pub fn log_clear() -> IpcResponse<()> {
    clear_logs();
    IpcResponse::ok(())
}

/// 写入一条日志到 Rust tracing 缓冲（供生命周期 / 前端主动上报）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
///
/// # 参数
///
/// * `message` — 日志正文
/// * `level` — 可选级别：TRACE / DEBUG / INFO / WARN / ERROR，默认 INFO
#[tauri::command]
pub fn log_write(app: AppHandle, message: String, level: Option<String>) -> IpcResponse<()> {
    let level = level.as_deref().unwrap_or("INFO");
    if let Err(error) = append_frontend_log_file(&app, level, &message) {
        warn!(target: FRONTEND_LOG_TARGET, %error, "写入前端日志文件失败");
    }
    if message.starts_with("访问页面") {
        on_route_change(&message);
        return IpcResponse::ok(());
    }
    match level {
        "ERROR" => error!(target: FRONTEND_LOG_TARGET, "{message}"),
        "WARN" => warn!(target: FRONTEND_LOG_TARGET, "{message}"),
        "DEBUG" | "TRACE" => debug!(target: FRONTEND_LOG_TARGET, "{message}"),
        _ => info!(target: FRONTEND_LOG_TARGET, "{message}"),
    }
    IpcResponse::ok(())
}
