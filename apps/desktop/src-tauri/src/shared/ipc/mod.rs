//! 全平台共用 IPC commands。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

pub mod agent;
pub mod ai;
pub mod app;
pub mod channel;
pub mod license;
pub mod log;
pub mod platform;
pub mod plugin;
pub mod response;

pub use agent::agent_reply;
pub use ai::{ai_account_balance, ai_config_get, ai_config_set, ai_test_api_key};
pub use app::{app_version, runtime_status, runtime_task_cancel};
pub use channel::{
    channel_connect, channel_disconnect, channel_send, channel_state_get, channel_state_set,
};
pub use license::{license_activate, license_machine_code, license_status};
pub use log::{log_clear, log_recent, log_write};
pub use platform::platform_descriptors;
pub use plugin::{plugin_install, plugin_list, plugin_uninstall};
pub use response::IpcResponse;
