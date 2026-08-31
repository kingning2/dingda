//! Tauri IPC commands — 按业务模块分目录导出；`lib.rs` 仅调用 [`invoke_handler!`]。

mod chain;

pub mod account;
pub mod agent;
pub mod app;
pub mod channel;
pub mod copilot;
pub mod manage;
pub mod response;

#[cfg(platform_xianyu)]
pub mod dashboard;
#[cfg(platform_xianyu)]
pub mod market;
#[cfg(platform_xianyu)]
pub mod setting;

pub use account::{
    account_create, account_delete, account_list, account_probe_login, account_qr_cancel,
    account_qr_check, account_qr_start, account_set_status, account_update, AccountHandle,
    AccountQrHandle, PostQrLoginHook,
};
pub use agent::{
    agent_reply, agent_run_cancel, agent_run_get, agent_run_list, agent_run_pause,
    agent_run_resume, agent_run_start, agent_run_status, ai_account_balance, ai_config_get,
    ai_config_set, ai_list_models, ai_providers_catalog, ai_test_api_key,
};
pub use app::{
    app_version, log_clear, log_recent, log_write, platform_descriptors, runtime_status,
    runtime_task_cancel,
};
#[cfg(platform_xianyu)]
pub use channel::{
    account_connect, account_connection_state, account_cookie_renew, account_disconnect,
    channel_fetch_history, channel_product_headinfo, channel_qr_cancel, channel_qr_check,
    channel_qr_start, sync_account_profile, to_channel_account,
};
pub use channel::{
    channel_connect, channel_disconnect, channel_send, channel_state_get, channel_state_set,
};
pub use copilot::{copilot_ready, copilot_run_abort, copilot_run_start};
#[cfg(platform_xianyu)]
pub use dashboard::{dashboard_stats, DashboardHandle};
pub use manage::{
    license_activate, license_machine_code, license_status, plugin_install, plugin_list,
    plugin_uninstall,
};
#[cfg(platform_xianyu)]
pub use market::{
    item_detail_fetch, item_get, item_list, item_sync, item_update, order_create, order_delete,
    order_get, order_list, order_update_delivery, order_update_status, ItemHandle, OrderHandle,
};
pub use response::IpcResponse;
#[cfg(platform_xianyu)]
pub use setting::{
    risk_config_get, risk_config_set, risk_log_clear, risk_log_clear_processing, risk_log_list,
    risk_log_today_rate, user_setting_get, user_setting_set, RiskHandle, UserSettingHandle,
};

#[cfg(not(any(platform_xianyu, platform_ali1688)))]
compile_error!("至少启用一个平台 feature（见 Cargo.toml [features]）");

/// `invoke_handler!` 所需的 `use` 声明。
#[macro_export]
macro_rules! invoke_ipc_use_decls {
    () => {
        use $crate::commands::*;
    };
}

/// 共享 + 账号等基础命令，交给 `$callback` 继续平台链。
#[macro_export]
macro_rules! with_shared_ipc {
    ($callback:ident) => {
        $callback!(
            agent_reply,
            agent_run_start,
            agent_run_pause,
            agent_run_resume,
            agent_run_cancel,
            agent_run_status,
            agent_run_get,
            agent_run_list,
            ai_config_get,
            ai_config_set,
            ai_providers_catalog,
            ai_list_models,
            ai_test_api_key,
            ai_account_balance,
            copilot_ready,
            copilot_run_start,
            copilot_run_abort,
            plugin_list,
            plugin_install,
            plugin_uninstall,
            account_list,
            account_create,
            account_update,
            account_set_status,
            account_delete,
            account_probe_login,
            account_qr_start,
            account_qr_check,
            account_qr_cancel,
            channel_state_get,
            channel_state_set,
            channel_connect,
            channel_disconnect,
            channel_send,
            license_status,
            license_machine_code,
            license_activate,
            platform_descriptors,
            log_clear,
            log_recent,
            log_write,
            app_version,
            runtime_status,
            runtime_task_cancel,
        )
    };
}

/// 组装 IPC handler：基础命令 → [`platform_ipc_chain!`]。
#[macro_export]
macro_rules! invoke_handler {
    () => {{
        $crate::invoke_ipc_use_decls!();
        $crate::with_shared_ipc!(platform_ipc_chain)
    }};
}
