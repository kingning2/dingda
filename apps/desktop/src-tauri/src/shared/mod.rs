//! Tauri 壳层共用模块 — 从 `dingda_business` re-export 纯业务代码。
//!
//! 本目录只保留 Tauri 专属胶水：
//! - `ipc/`：所有 `#[tauri::command]`
//! - `state.rs`：`AppState`（持有 Tauri 类型的共享状态）
//! - `channel/coordinator.rs`：协调器（依赖 `tauri::Emitter`）
//! - `shell_platform.rs`：Tauri 初始化脚本注入
//! - `compile.rs`：平台编译期常量 re-export
//!
//! App 生命周期观测已移至 `crate::runtime::app`（`[startup]` / 窗口 / 路由日志）。
//! 纯 Rust 业务逻辑已移至 `dingda-business` crate，通过 re-export 向 IPC 层暴露。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

pub mod channel;
pub mod compile;
pub mod event_bridge;
pub mod event_sink;
pub mod ipc;
pub mod plugin_download;
pub mod shell_platform;
pub mod state;

// 从 dingda-business re-export，保持 IPC 层路径不变
pub use business::config;
pub use business::logging;
pub use business::timing;
pub use event_bridge::BusToTauri;
pub use event_sink::TauriEventSink;

#[allow(unused_imports)]
pub use compile::{active_kind, is_active, is_active_id, ACTIVE_PLATFORM};
pub use logging::init_tracing;
pub use shell_platform::platform_initialization_script;
pub use state::{build_license_gate, AppState};
