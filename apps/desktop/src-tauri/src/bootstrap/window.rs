//! 壳层窗口与 OS 平台 — 路由观测、平台装配、平台标签。
//!
//! 由 `route.rs` + `platform.rs` + `shell_platform.rs` 合并而来。

// ── 路由切换观测 ──

/// 记录工作区路由访问（由 `log_write` IPC 或内部调用）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
///
/// # 参数
///
/// * `message` — 已格式化的访问描述
pub fn on_route_change(message: &str) {
    info!(target: "dingda.lifecycle", "{message}");
}

// ── 平台运行时装配 ──

use crate::application::channel::coordinator::ChannelCoordinator;
use crate::application::channel::dispatcher::ChannelDispatcher;
use crate::commands::{
    sync_account_profile, to_channel_account, AccountHandle, AccountQrHandle, DashboardHandle,
    ItemHandle, OrderHandle, PostQrLoginHook, RiskHandle, UserSettingHandle,
};
use crate::contracts::DingDaResult;
use crate::infrastructure::channel::wss_bridge::connect_channel;
use crate::infrastructure::channel::PythonWssBridge;
use crate::infrastructure::database::{
    InMemoryItemStore, InMemoryOrderStore, InMemoryRiskStore, InMemoryUserSettingStore,
    SqliteBusinessDb,
};
use std::sync::Arc;
use tauri::Manager;

/// 注册平台专属业务 Handle（闲鱼商品/订单/风控 Store 等）。
pub fn register_platform(
    app: &tauri::AppHandle,
    dispatcher: &Arc<ChannelDispatcher>,
    coordinator: &Arc<ChannelCoordinator>,
    wss_bridge: &Arc<PythonWssBridge>,
) -> DingDaResult<()> {
    #[cfg(platform_xianyu)]
    {
        register_xianyu_business(app, wss_bridge)?;
        // 进程内渠道调度器为占位（闲鱼连接由 Python Sidecar WSS 负责）。
        let _ = (dispatcher, coordinator);
    }
    #[cfg(not(platform_xianyu))]
    {
        let _ = (app, dispatcher, coordinator, wss_bridge);
    }
    Ok(())
}

/// 账号 CRUD / 扫码登录等两站共用 Handle 由 `core::bootstrap` 无条件注册；
/// 本函数仅注册闲鱼专属 Handle，并把扫码后置逻辑写入共用 `AccountQrHandle.post_login`。
#[cfg(platform_xianyu)]
fn register_xianyu_business(
    app: &tauri::AppHandle,
    wss_bridge: &Arc<PythonWssBridge>,
) -> DingDaResult<()> {
    let db = app.state::<Arc<SqliteBusinessDb>>();
    let accounts = app.state::<AccountHandle>().store.clone();

    let items = Arc::new(InMemoryItemStore::new((**db).clone()));
    let orders = Arc::new(InMemoryOrderStore::new((**db).clone()));

    app.manage(OrderHandle {
        store: orders.clone(),
    });
    app.manage(ItemHandle {
        store: items.clone(),
    });
    app.manage(UserSettingHandle {
        store: Arc::new(InMemoryUserSettingStore::new((**db).clone())),
    });
    app.manage(DashboardHandle {
        accounts,
        items,
        orders,
    });
    app.manage(RiskHandle {
        store: Arc::new(InMemoryRiskStore::new((**db).clone())),
    });

    let wss_bridge = wss_bridge.clone();
    let lifecycle = app
        .state::<crate::bootstrap::state::AppState>()
        .lifecycle
        .clone();
    let post_login: PostQrLoginHook = Arc::new(move |dispatcher, store, owner_id, account| {
        let wss_bridge = wss_bridge.clone();
        let lifecycle = lifecycle.clone();
        Box::pin(async move {
            if account.platform != "xianyu" {
                return Ok(());
            }
            let channel_account = to_channel_account(owner_id, &account);
            connect_channel(wss_bridge.as_ref(), dispatcher.as_ref(), &channel_account)
                .await
                .map_err(crate::contracts::DingDaError::wrap)?;
            if let Err(error) =
                sync_account_profile(lifecycle.as_ref(), &store, owner_id, &account.account_id)
                    .await
            {
                warn!(
                    account = %account.account_id,
                    %error,
                    "扫码后拉取闲鱼用户资料失败"
                );
            }
            Ok(())
        })
    });
    let qr_handle = app.state::<AccountQrHandle>();
    *qr_handle
        .post_login
        .write()
        .unwrap_or_else(|poisoned| poisoned.into_inner()) = Some(post_login);

    Ok(())
}

// ── OS 平台标签 ──

/// 当前运行 OS 对应的桌面平台标签（与前端 `DesktopPlatform` 对齐）。
///
/// 作者：coisini
/// 创建时间：2026-07-21
///
/// # 返回值
/// `"macos"` / `"windows"` / `"linux"`。
pub fn desktop_platform_label() -> &'static str {
    match std::env::consts::OS {
        "macos" => "macos",
        "windows" => "windows",
        _ => "linux",
    }
}

/// 在页面脚本执行前注入 `window.__DINGDA_PLATFORM__` 的初始化脚本。
///
/// 作者：coisini
/// 创建时间：2026-07-21
///
/// # 返回值
/// 可传给 `append_invoke_initialization_script` 的 JS 字符串。
pub fn platform_initialization_script() -> String {
    format!(
        r#"Object.defineProperty(window,"__DINGDA_PLATFORM__",{{value:"{}",writable:false,configurable:false}});"#,
        desktop_platform_label()
    )
}
