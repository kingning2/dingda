//! IPC 注册链 — 平台顺序在此维护；新增平台追加一步 link。
//!
//! 顺序：`xianyu` → `ali1688` → `finish`

/// 共享命令入口 → 链首站。
#[macro_export]
macro_rules! platform_ipc_chain {
    ($($shared:tt)*) => {
        $crate::platform_ipc_step_xianyu!($($shared)*)
    };
}

/// 闲鱼之后 → 1688。
#[macro_export]
macro_rules! platform_ipc_link_after_xianyu {
    ($($cmds:tt)*) => {
        $crate::platform_ipc_step_ali1688!($($cmds)*)
    };
}

/// 1688 之后 → 收尾。
#[macro_export]
macro_rules! platform_ipc_link_after_ali1688 {
    ($($cmds:tt)*) => {
        $crate::platform_ipc_chain_finish!($($cmds)*)
    };
}

/// 链尾：`generate_handler!`。
#[macro_export]
macro_rules! platform_ipc_chain_finish {
    ($($cmds:tt)*) => {
        tauri::generate_handler![ $($cmds)* ]
    };
}

#[cfg(platform_xianyu)]
#[macro_export]
macro_rules! platform_ipc_step_xianyu {
    ($($prior:tt)*) => {
        $crate::platform_ipc_link_after_xianyu!(
            $($prior)*
            account_connect,
            account_cookie_renew,
            account_disconnect,
            account_connection_state,
            order_list,
            order_get,
            order_update_status,
            order_update_delivery,
            order_create,
            order_delete,
            item_list,
            item_get,
            item_update,
            item_sync,
            item_detail_fetch,
            risk_log_list,
            risk_log_today_rate,
            risk_log_clear,
            risk_log_clear_processing,
            risk_config_get,
            risk_config_set,
            user_setting_get,
            user_setting_set,
            dashboard_stats,
            channel_fetch_history,
            channel_product_headinfo,
            channel_qr_start,
            channel_qr_check,
            channel_qr_cancel,
        )
    };
}

#[cfg(not(platform_xianyu))]
#[macro_export]
macro_rules! platform_ipc_step_xianyu {
    ($($prior:tt)*) => {
        $crate::platform_ipc_link_after_xianyu!($($prior)*)
    };
}

#[cfg(platform_ali1688)]
#[macro_export]
macro_rules! platform_ipc_step_ali1688 {
    ($($prior:tt)*) => {
        $crate::platform_ipc_link_after_ali1688!(
            $($prior)*
        )
    };
}

#[cfg(not(platform_ali1688))]
#[macro_export]
macro_rules! platform_ipc_step_ali1688 {
    ($($prior:tt)*) => {
        $crate::platform_ipc_link_after_ali1688!($($prior)*)
    };
}
