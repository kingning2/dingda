//! 跨层共用模块（对标 clash-verge-rev `utils/`）。
//!
//! - `state.rs`：`AppState`
//! - `channel_store.rs`：渠道持久化存储
//! - `shell_platform.rs`：Tauri 初始化脚本注入
//! - 根级 `constants.rs`：平台编译期常量 re-export
//!
//! IPC 命令在 [`crate::cmd`]。

pub mod channel_store;
pub mod event_bridge;
pub mod event_sink;
pub mod kernel_event_sink;
pub mod logging;
pub mod plugin_download;
pub mod shell_platform;
pub mod state;
pub mod timing;

pub use event_bridge::BusToTauri;
pub use event_sink::TauriEventSink;
pub use logging::init_tracing;
pub use shell_platform::platform_initialization_script;
pub use state::AppState;
