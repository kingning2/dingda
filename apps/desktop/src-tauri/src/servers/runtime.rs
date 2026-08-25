//! 平台运行时装配 — 业务 Handle、渠道协议注册。
//!
//! 条件编译收敛在本模块；`lib.rs` setup 仅调用 [`register_platform`]。

use crate::contracts::DingDaResult;
use crate::runtime::python::PythonWssBridge;
use crate::shared::channel::coordinator::ChannelCoordinator;
use crate::shared::channel::dispatcher::ChannelDispatcher;
use std::sync::Arc;

#[cfg(platform_xianyu)]
use tauri::Manager;

/// 注册平台专属业务 Handle（闲鱼监控 / 风控日志 Store 等）。
pub fn register_platform(
    app: &tauri::AppHandle,
    dispatcher: &Arc<ChannelDispatcher>,
    coordinator: &Arc<ChannelCoordinator>,
    wss_bridge: &Arc<PythonWssBridge>,
) -> DingDaResult<()> {
    #[cfg(platform_xianyu)]
    {
        crate::servers::xianyu::bootstrap::register_business(app, wss_bridge)?;
        let account_store = app
            .try_state::<crate::command::AccountHandle>()
            .map(|handle| handle.store.clone());
        crate::servers::xianyu::bootstrap::register_active_platform(
            dispatcher,
            coordinator,
            account_store,
        );
    }
    #[cfg(not(platform_xianyu))]
    {
        let _ = (app, dispatcher, coordinator, wss_bridge);
    }
    Ok(())
}
