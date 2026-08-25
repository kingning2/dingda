//! 运行日志 IPC 命令 — 供前端日志面板读取/清空/写入进程内日志缓冲。

use crate::command::IpcResponse;
use crate::logging::{clear_logs, recent_logs, LogEntry};
use crate::runtime::app::route::on_route_change;
use chrono::Local;
use std::fs::{self, OpenOptions};
use std::io::Write;
use tauri::{AppHandle, Manager};

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
