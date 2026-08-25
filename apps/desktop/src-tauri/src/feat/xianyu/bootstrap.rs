//! 闲鱼壳层启动：注册业务 Handle、注册渠道协议。
//!
//! 账号 CRUD / 扫码登录等两站共用 Handle 由 `core::bootstrap` 无条件注册；
//! 本模块仅注册闲鱼专属 Handle，并把扫码后置逻辑写入共用 `AccountQrHandle.post_login`。
//! 风控续期在 Python WSS 内完成。

use crate::cmd::{
    sync_account_profile, to_channel_account, AccountHandle, AccountQrHandle, DashboardHandle,
    ItemHandle, MonitorHandle, OrderHandle, PostQrLoginHook, RiskHandle, UserSettingHandle,
};
use crate::contracts::DingDaResult;
use crate::core::manager::python::wss_bridge::connect_channel;
use crate::core::manager::python::PythonWssBridge;
use crate::core::store::{
    InMemoryItemStore, InMemoryMonitorResultStore, InMemoryMonitorRunStore,
    InMemoryMonitorTaskStore, InMemoryOrderStore, InMemoryRiskStore, InMemoryUserSettingStore,
    SqliteBusinessDb,
};
use std::sync::Arc;
use tauri::Manager;

/// 注册闲鱼专属 Handle + 写入扫码后置逻辑。
pub fn register_business(
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

    let monitor_tasks = Arc::new(InMemoryMonitorTaskStore::new((**db).clone()));
    let monitor_results = Arc::new(InMemoryMonitorResultStore::new((**db).clone()));
    let monitor_runs = Arc::new(InMemoryMonitorRunStore::new((**db).clone()));
    let app_state = Arc::new(app.state::<crate::utils::state::AppState>().inner().clone());
    let engine = Arc::new(crate::feat::xianyu::monitor::MonitorEngine {
        tasks: monitor_tasks.clone(),
        results: monitor_results.clone(),
        runs: monitor_runs.clone(),
        app_state: app_state.clone(),
        account_store: app.state::<AccountHandle>().store.clone(),
        config_store: app
            .state::<Arc<crate::config::ConfigStore>>()
            .inner()
            .clone(),
        sidecar: app_state.lifecycle.clone(),
        event_sink: app
            .state::<Arc<dyn crate::contracts::events::EventSink>>()
            .inner()
            .clone(),
    });
    engine.recover_interrupted_runs(1)?;
    let task_manager = app
        .state::<crate::utils::state::AppState>()
        .supervisor
        .tasks()
        .clone();
    let scheduler = Arc::new(crate::feat::xianyu::monitor::MonitorScheduler::new(
        engine.clone(),
        1,
        task_manager,
    ));
    scheduler.clone().start();
    app.manage(MonitorHandle {
        tasks: monitor_tasks,
        results: monitor_results,
        runs: monitor_runs,
        engine,
    });

    let wss_bridge = wss_bridge.clone();
    let lifecycle = app
        .state::<crate::utils::state::AppState>()
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
