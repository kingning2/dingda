//! Tauri IPC handler 注册 — 共享 / core 在此列出，平台专属由各站 `platform_ipc_step_*` 导出。
//!
//! 平台链顺序见 [`chain`]；`lib.rs` 仅调用 [`invoke_handler!`]。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-22

mod chain;

// 与 `tooling/config/channel-platforms.json` / Cargo features 对齐；新增平台时追加 cfg。
#[cfg(not(any(
    platform_xianyu,
    platform_ali1688,
    // platform_xiaohongshu,
    // platform_douyin,
)))]
compile_error!("至少启用一个平台 feature（见 Cargo.toml [features]）");

/// `invoke_handler!` 所需的 `use` 声明（各平台 IPC 按 cfg 引入）。
#[macro_export]
macro_rules! invoke_ipc_use_decls {
    () => {
        #[cfg(platform_ali1688)]
        use $crate::platforms::ali1688::ipc::ali1688_search;
        use $crate::platforms::core::{
            account_create, account_delete, account_list, account_probe_login, account_qr_cancel,
            account_qr_check, account_qr_start, account_set_status, account_update,
        };
        #[cfg(platform_xianyu)]
        use $crate::platforms::xianyu::ipc::*;
        use $crate::shared::ipc::{
            agent_reply, ai_account_balance, ai_config_get, ai_config_set, ai_test_api_key,
            app_version, channel_connect, channel_disconnect, channel_send, channel_state_get,
            channel_state_set, license_activate, license_machine_code, license_status, log_clear,
            log_recent, log_write, platform_descriptors, plugin_install, plugin_list,
            plugin_uninstall, runtime_status, runtime_task_cancel,
        };
        // 1688 专属 IPC 落地后在此 `use` 并在 `platform_ipc_step_ali1688!` 中追加命令名。
    };
}

/// 共享 + core IPC 命令列表，交给 `$callback` 宏继续平台链。
#[macro_export]
macro_rules! with_shared_ipc {
    ($callback:ident) => {
        $callback!(
            agent_reply,
            ai_config_get,
            ai_config_set,
            ai_test_api_key,
            ai_account_balance,
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

/// 组装 IPC handler：共享 + core → [`platform_ipc_chain!`]。
#[macro_export]
macro_rules! invoke_handler {
    () => {{
        $crate::invoke_ipc_use_decls!();
        $crate::with_shared_ipc!(platform_ipc_chain)
    }};
}
