//! Runtime 控制层 — 按实际运行时对象拆分生命周期。
//!
//! 结构：
//! - [`app`] — Tauri App 生命周期（观测层：`[startup]` / 窗口 / 页面 / 路由 / RunEvent）
//! - [`python`] — Python Runtime 生命周期（状态 / 进程 / IPC / 健康）
//! - [`agent`] — Agent Runtime 生命周期（状态机 / 管理）
//! - [`tasks`] — 异步任务生命周期（状态 / 阶段 / 管理器 / 执行器 / 取消）
//! - [`supervisor`] — 总协调器（`RuntimeSupervisor`）
//! - [`state`] — Runtime 全局状态
//! - [`shutdown`] — 统一关闭流程
//!
//! 日志约定：App 观测走 `[startup]`（`app::startup`），运行时控制走 `[runtime]`（`RUNTIME_TARGET`）。

pub mod agent;
pub mod app;
pub mod python;
pub mod shutdown;
pub mod state;
pub mod supervisor;
pub mod tasks;

pub use state::RuntimeState;
pub use supervisor::RuntimeSupervisor;

/// `[runtime]` 日志 target — 与观测层 `[startup]`（`dingda.lifecycle`）区分。
pub const RUNTIME_TARGET: &str = "dingda.runtime";
