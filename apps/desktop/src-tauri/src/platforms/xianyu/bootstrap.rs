//! 闲鱼壳层启动：注册业务 Handle、装配风控、注册渠道协议。
//!
//! 账号 CRUD / 扫码登录等两站共用 Handle 由 `platforms::core::bootstrap` 无条件注册；
//! 本模块仅注册闲鱼专属 Handle（商品 / 订单 / 风控 / 用户设置 / 仪表盘），
//! 并把闲鱼扫码后置逻辑写入共用的 `AccountQrHandle.post_login`。
//!
//! 精简说明：发布 / 卡券 / 黑名单 / 关键词 / 消息过滤 / 通知 / 反馈 / 评价等
//! 子页已下线，对应 Store Handle 一并移除。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use crate::platforms::core::account::AccountHandle;
use crate::platforms::core::account_qr::{AccountQrHandle, PostQrLoginHook};
use crate::platforms::xianyu::ipc;
use crate::shared::channel::coordinator::ChannelCoordinator;
use crate::shared::channel::risk_handler::RiskHandler;
use common::events::EventSink;
use common::DingDaResult;
use platform::domain::account::AccountStore;
use platform::protocol::dispatcher::ChannelDispatcher;
use platform::protocol::{ChannelKind, ChannelProtocol};
use platform::shared::{
    InMemoryAccountStore, InMemoryItemStore, InMemoryMonitorResultStore, InMemoryMonitorRunStore,
    InMemoryMonitorTaskStore, InMemoryOrderStore, InMemoryRiskStore, InMemoryUserSettingStore,
    SqliteBusinessDb,
};
use platform::xianyu::XianyuChannel;
use std::sync::Arc;
use tauri::Manager;

/// 注册闲鱼专属 Handle + 写入扫码后置逻辑。
///
/// 业务库与账号 Handle 已由 `platforms::core::bootstrap::register_business` 注册，
/// 此处仅注册闲鱼专属 Handle，并把闲鱼扫码后置逻辑写入共用 `AccountQrHandle`。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
///
/// # 参数
///
/// * `app` — Tauri 应用句柄
///
/// # 返回值
///
/// 成功返回 `()`；注册失败返回错误文案。
pub fn register_business(app: &tauri::AppHandle) -> DingDaResult<()> {
    let db = app.state::<Arc<SqliteBusinessDb>>();
    let accounts = app.state::<AccountHandle>().store.clone();

    let items = Arc::new(InMemoryItemStore::new((**db).clone()));
    let orders = Arc::new(InMemoryOrderStore::new((**db).clone()));

    app.manage(ipc::order::OrderHandle {
        store: orders.clone(),
    });
    app.manage(ipc::item::ItemHandle {
        store: items.clone(),
    });
    app.manage(ipc::setting::UserSettingHandle {
        store: Arc::new(InMemoryUserSettingStore::new((**db).clone())),
    });
    app.manage(ipc::dashboard::DashboardHandle {
        accounts,
        items,
        orders,
    });

    let monitor_tasks = Arc::new(InMemoryMonitorTaskStore::new((**db).clone()));
    let monitor_results = Arc::new(InMemoryMonitorResultStore::new((**db).clone()));
    let monitor_runs = Arc::new(InMemoryMonitorRunStore::new((**db).clone()));
    let engine = Arc::new(crate::platforms::xianyu::monitor::MonitorEngine {
        tasks: monitor_tasks.clone(),
        results: monitor_results.clone(),
        runs: monitor_runs.clone(),
        app_state: Arc::new(
            app.state::<crate::shared::state::AppState>()
                .inner()
                .clone(),
        ),
        account_store: app.state::<AccountHandle>().store.clone(),
        config_store: app
            .state::<Arc<crate::config::ConfigStore>>()
            .inner()
            .clone(),
        event_sink: app
            .state::<Arc<dyn common::events::EventSink>>()
            .inner()
            .clone(),
    });
    // 清理上次中断残留的 is_running / running 运行记录，避免「立即运行」被卡死。
    engine.recover_interrupted_runs(1)?;
    let task_manager = app
        .state::<crate::shared::state::AppState>()
        .supervisor
        .tasks()
        .clone();
    let scheduler = Arc::new(crate::platforms::xianyu::monitor::MonitorScheduler::new(
        engine.clone(),
        1,
        task_manager,
    ));
    scheduler.clone().start();
    app.manage(ipc::monitor::MonitorHandle {
        tasks: monitor_tasks,
        results: monitor_results,
        runs: monitor_runs,
        engine,
    });

    // 扫码成功后置逻辑：闲鱼账号自动建渠道 WS 并拉取用户资料。
    // 1688 账号（双站构建下同一 handle 共用）不连闲鱼 WS，直接跳过。
    let post_login: PostQrLoginHook = Arc::new(|dispatcher, store, owner_id, account| {
        Box::pin(async move {
            use crate::platforms::xianyu::ipc::account_connection;
            if account.platform != "xianyu" {
                return Ok(());
            }
            let channel_account = account_connection::to_channel_account(owner_id, &account);
            dispatcher
                .connect(&channel_account)
                .await
                .map_err(common::DingDaError::wrap)?;
            if let Err(error) =
                account_connection::sync_account_profile(&store, owner_id, &account.account_id)
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

/// 装配闲鱼风控：风控存储、滑块续期器、风控处理实现。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-22
///
/// # 参数
///
/// * `app` — Tauri 应用句柄
/// * `dispatcher` — 渠道调度器
/// * `event_sink` — 事件下发
///
/// # 返回值
///
/// 闲鱼风控处理（`Arc<dyn RiskHandler>`）。
pub fn build_risk_handler(
    app: &tauri::AppHandle,
    dispatcher: &Arc<ChannelDispatcher>,
    event_sink: Arc<dyn EventSink>,
) -> Arc<dyn RiskHandler> {
    let db = app.state::<Arc<SqliteBusinessDb>>();
    let risk_store = Arc::new(InMemoryRiskStore::new((**db).clone()));
    app.manage(ipc::risk::RiskHandle {
        store: risk_store.clone(),
    });

    let account_store: Arc<dyn AccountStore> = app.state::<AccountHandle>().store.clone();
    let app_state = app.state::<crate::shared::state::AppState>();
    let renewer = Arc::new(
        crate::platforms::xianyu::cookie_renew::RiskCookieRenewer::new(
            app_state.lifecycle.clone(),
            account_store,
            dispatcher.clone(),
            Some(risk_store.clone()),
            event_sink.clone(),
            1,
            app_state.supervisor.tasks().clone(),
        ),
    );
    app.manage(renewer.clone());

    Arc::new(crate::platforms::xianyu::risk::XianyuRiskHandler::new(
        Some(risk_store),
        Some(renewer),
        event_sink,
        1,
    ))
}

/// 向调度器注册闲鱼渠道协议，并绑定入站监听器。
///
/// 开发态默认走帧隧道 Host（`127.0.0.1:10050`）：上游 WSS 在 Host，协议在本进程。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
///
/// # 参数
///
/// * `dispatcher` — 渠道调度器
/// * `coordinator` — 入站协调器（作为协议监听器）
/// * `account_store` — 用于启动后自动附着 Host 已有会话
///
/// # 返回值
///
/// 无；副作用是把闲鱼协议注册进调度器。
pub fn register_active_platform(
    dispatcher: &Arc<ChannelDispatcher>,
    coordinator: &Arc<ChannelCoordinator>,
    account_store: Option<Arc<InMemoryAccountStore>>,
) {
    #[cfg(debug_assertions)]
    {
        if common::constants::FeatureFlags::from_env().dev_channel_host {
            match crate::platforms::xianyu::dev_host::ensure_dev_channel_host() {
                Ok(()) => {
                    let listener = coordinator.clone();
                    dispatcher.register_factory(
                        ChannelKind::Xianyu,
                        Arc::new(move || {
                            let channel = Arc::new(XianyuChannel::new_dev_tunnel());
                            channel.set_inbound_listener(listener.clone());
                            channel
                        }),
                    );
                    tracing::info!(
                        "闲鱼协议使用开发态帧隧道（Host 持有 WSS，本进程持有协议所有权）"
                    );
                    let dispatcher = dispatcher.clone();
                    let store = account_store;
                    tauri::async_runtime::spawn(async move {
                        let accounts = store
                            .and_then(|store| store.list_accounts(1).ok())
                            .unwrap_or_default()
                            .into_iter()
                            .filter(|account| account.has_cookie())
                            .map(|account| {
                                let name = if account.display_name.is_empty() {
                                    account.account_id.clone()
                                } else {
                                    account.display_name.clone()
                                };
                                (account.account_id, account.cookie, name)
                            })
                            .collect();
                        crate::platforms::xianyu::dev_host::reattach_host_sessions(
                            dispatcher, accounts,
                        )
                        .await;
                    });
                    return;
                }
                Err(error) => {
                    tracing::warn!(%error, "Channel Host 不可用，回退进程内直连");
                }
            }
        }
    }

    let listener = coordinator.clone();
    dispatcher.register_factory(
        ChannelKind::Xianyu,
        Arc::new(move || {
            let channel = Arc::new(XianyuChannel::new());
            channel.set_inbound_listener(listener.clone());
            channel
        }),
    );
}
