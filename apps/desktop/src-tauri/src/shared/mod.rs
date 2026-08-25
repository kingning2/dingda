//! Tauri 壳层共用模块。
//!
//! - `state.rs`：`AppState`
//! - `channel/`：协调器 / 调度器
//! - `shell_platform.rs`：Tauri 初始化脚本注入
//! - `compile.rs`：平台编译期常量 re-export
//!
//! IPC 命令在 [`crate::command`]。

pub mod channel;
pub mod compile;
pub mod event_bridge;
pub mod event_sink;
pub mod plugin_download;
pub mod shell_platform;
pub mod state;

pub use event_bridge::BusToTauri;
pub use event_sink::TauriEventSink;

pub use crate::logging::init_tracing;
#[allow(unused_imports)]
pub use compile::{active_kind, is_active, is_active_id, ACTIVE_PLATFORM};
pub use shell_platform::platform_initialization_script;
pub use state::AppState;
