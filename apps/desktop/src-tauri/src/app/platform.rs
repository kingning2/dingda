//! 平台运行时装配 — 业务 Handle、渠道协议注册。
//!
//! 条件编译收敛在本模块；`lib.rs` setup 仅调用 [`register_platform`]。

use crate::application::channel::coordinator::ChannelCoordinator;
use crate::application::channel::dispatcher::ChannelDispatcher;
use crate::commands::{
    sync_account_profile, to_channel_account, AccountHandle, AccountQrHandle, DashboardHandle,
    ItemHandle, OrderHandle, PostQrLoginHook, RiskHandle, UserSettingHandle,
};
use crate::contracts::DingDaResult;
use crate::infrastructure::channel::wss_bridge::connect_channel;
use crate::infrastructure::channel::PythonWssBridge;
use crate::infrastructure::storage::{
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
    let lifecycle = app.state::<crate::app::state::AppState>().lifecycle.clone();
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
