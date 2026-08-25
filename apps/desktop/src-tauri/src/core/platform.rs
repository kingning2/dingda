//! 平台运行时装配 — 业务 Handle、渠道协议注册。
//!
//! 条件编译收敛在本模块；`lib.rs` setup 仅调用 [`register_platform`]。

use crate::contracts::DingDaResult;
use crate::core::channel::coordinator::ChannelCoordinator;
use crate::core::channel::dispatcher::ChannelDispatcher;
use crate::core::manager::python::PythonWssBridge;
use std::sync::Arc;

/// 注册平台专属业务 Handle（闲鱼监控 / 风控日志 Store 等）。
pub fn register_platform(
    app: &tauri::AppHandle,
    dispatcher: &Arc<ChannelDispatcher>,
    coordinator: &Arc<ChannelCoordinator>,
    wss_bridge: &Arc<PythonWssBridge>,
) -> DingDaResult<()> {
    #[cfg(platform_xianyu)]
    {
        crate::feat::xianyu::bootstrap::register_business(app, wss_bridge)?;
        // 进程内渠道调度器为占位（闲鱼连接由 Python Sidecar WSS 负责）。
        let _ = (dispatcher, coordinator);
    }
    #[cfg(not(platform_xianyu))]
    {
        let _ = (app, dispatcher, coordinator, wss_bridge);
    }
    Ok(())
}
