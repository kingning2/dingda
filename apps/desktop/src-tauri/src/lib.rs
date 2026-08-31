//! Tauri shell：组装 AppState、注册 IPC commands、启动 sidecar。
//!
//! 目录约定（六边形 + Tauri）：
//! - [`commands`] — Tauri IPC 薄适配层
//! - [`domain`] — 纯领域（实体 / 协议）
//! - [`application`] — 用例编排
//! - [`ports`] — Port traits
//! - [`infrastructure`] — Driven 适配器（存储 / 事件 / runtime / 渠道 IO）
//! - [`bootstrap`] — 壳层状态与生命周期观测
//! - [`config`] / [`contracts`] — 配置与共享 DTO
//!
//! 本文件仅负责 AppState 组装与 Tauri 生命周期编排。
//!
//! 作者：Xiaoman
//! 创建时间：2026-07-16

#[macro_use]
extern crate tracing;

pub mod application;
pub mod bootstrap;
pub mod commands;
pub mod config;
pub mod constants;
pub mod contracts;
pub mod core;
pub mod domain;
pub mod infrastructure;
pub mod ports;

// 兼容路径：`crate::state` → `app::state`（AppState）。
pub use bootstrap::state;

use crate::application::channel::coordinator::ChannelCoordinator;
use crate::bootstrap::lifecycle;
use crate::domain::channel::ChannelDispatcher;
use crate::infrastructure::channel::PythonWssBridge;
use crate::infrastructure::database::ChannelRepo;
use crate::infrastructure::event::{BusToTauri, EventBus, InMemoryEventBus, TauriEventSink};
use crate::infrastructure::sidecar::RuntimeAgentSidecar;
use crate::infrastructure::sidecar::{
    SidecarConfig, SidecarLifecycle, RUNTIME_ERROR_TOPIC, SIDECAR_RESTARTED_TOPIC,
};
use crate::ports::license::LicenseGate;
use bootstrap::{init_tracing, platform_initialization_script, AppState};
use std::path::PathBuf;
use std::sync::Arc;
use tauri::{Manager, RunEvent};

/// 启动桌面应用：组装 AppState、注册 IPC、运行事件循环。
///
/// 作者：coisini
/// 创建时间：2026-07-16
///
/// # 参数
/// - `context` — Tauri 构建上下文
///
/// # 返回值
/// 事件循环结束后的 `tauri::Result`。
pub fn launch(
    context: tauri::Context<tauri::Wry>,
    license: Arc<dyn LicenseGate>,
) -> tauri::Result<()> {
    init_tracing();
    lifecycle::on_process_start();

    let event_bus = Arc::new(InMemoryEventBus::new());
    let lifecycle = Arc::new(SidecarLifecycle::new(
        SidecarConfig::from_env(),
        event_bus.clone() as Arc<dyn EventBus>,
    ));
    let gateway = Arc::new(RuntimeAgentSidecar::new(lifecycle.client().clone()));
    let supervisor = Arc::new(crate::core::RuntimeSupervisor::new(lifecycle.clone()));
    let app_state = AppState {
        lifecycle: lifecycle.clone(),
        gateway,
        license,
        event_bus,
        supervisor,
    };
    lifecycle::on_state_ready();

    let mut builder = tauri::Builder::default();
    #[cfg(any(target_os = "macos", windows, target_os = "linux"))]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            info!("检测到重复启动，聚焦已有窗口");
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            } else if let Some((_, window)) = app.webview_windows().into_iter().next() {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }));
    }

    builder
        .plugin(tauri_plugin_opener::init())
        .append_invoke_initialization_script(platform_initialization_script())
        .manage(app_state)
        .on_page_load(|_webview, payload| {
            lifecycle::on_page_load(payload.event(), payload.url().as_str())
        })
        .on_window_event(lifecycle::on_window_event)
        .setup(move |app| {
            lifecycle::on_setup_begin();
            let windows = app.webview_windows();
            if windows.is_empty() {
                lifecycle::on_window_none();
            } else {
                for (label, window) in windows {
                    let visible = window.is_visible().unwrap_or(false);
                    lifecycle::on_window_ready(&label, visible);
                }
            }
            let config_dir = match app.path().app_config_dir() {
                Ok(dir) => dir,
                Err(error) => {
                    error!(%error, "解析应用配置目录失败；AI 配置已禁用");
                    PathBuf::from(".")
                }
            };
            let data_dir = match app.path().app_local_data_dir() {
                Ok(dir) => dir,
                Err(error) => {
                    error!(%error, "解析本地数据目录失败；插件将写入配置目录");
                    config_dir.clone()
                }
            };
            let config_store = Arc::new(crate::config::ConfigStore::new(
                config_dir.clone(),
                data_dir,
            ));
            crate::infrastructure::plugins::download::sync_camoufox_env(&config_store);
            lifecycle::on_plugin_env_ready();
            app.manage(config_store.clone());
            let plugin_tracker =
                Arc::new(crate::infrastructure::plugins::download::PluginDownloadTracker::new());
            app.manage(plugin_tracker);

            // Embedding：独立 manage，安装与推理共用同一实例（OnceLock 预热后可复用）
            let embedder = Arc::new(crate::infrastructure::embedding::EmbeddingService::new(
                crate::config::embedding_cache_dir(config_store.plugins_dir()),
            ));
            app.manage(embedder);

            // 侧车后台异步拉起：不阻塞窗口 / HTML；watchdog 等首次 start 完成后再开，避免双 spawn 抢 pipe。
            let supervisor = app.state::<AppState>().supervisor.clone();
            let supervisor_boot = supervisor.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(error) = supervisor_boot.start().await {
                    error!(%error, "Runtime 后台启动失败；业务将按需自愈");
                }
                supervisor_boot.spawn_observation_loop();
            });

            crate::application::bootstrap::register_business(app.handle(), &config_dir)?;
            lifecycle::on_business_ready();

            let db_dir = config_dir.join("channel");
            std::fs::create_dir_all(&db_dir).ok();
            let repo = match ChannelRepo::open(
                &db_dir.join("channel.db"),
                &PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("migrations"),
            ) {
                Ok(repo) => Arc::new(repo),
                Err(error) => {
                    error!(%error, "打开渠道数据库失败；渠道已禁用");
                    return Ok(());
                }
            };
            app.manage(repo.clone());
            lifecycle::on_channel_db_ready();

            let dispatcher = Arc::new(ChannelDispatcher::new());
            app.manage(dispatcher.clone());

            let event_sink: Arc<dyn crate::contracts::events::EventSink> =
                Arc::new(TauriEventSink::new(app.handle().clone()));
            app.manage(event_sink.clone());

            {
                let agent_store = Arc::new(crate::infrastructure::sidecar::AgentRunStore::new(
                    config_dir.clone(),
                ));
                let account_store = app.state::<crate::commands::AccountHandle>().store.clone();
                app.state::<AppState>().supervisor.agent().configure(
                    event_sink.clone(),
                    config_store.clone(),
                    agent_store,
                    account_store,
                );
                app.state::<AppState>()
                    .supervisor
                    .agent()
                    .spawn_pipe_listener();
                crate::infrastructure::sidecar::copilot_runtime::spawn_copilot_pipe_listener_from_lifecycle(
                    app.state::<AppState>().lifecycle.clone(),
                    app.handle().clone(),
                );
            }

            {
                let forwarder = BusToTauri::new(app.handle().clone());
                for topic in [RUNTIME_ERROR_TOPIC, SIDECAR_RESTARTED_TOPIC] {
                    if let Err(error) = app
                        .state::<AppState>()
                        .event_bus
                        .subscribe(topic, Box::new(forwarder.clone()))
                    {
                        error!(%error, %topic, "runtime 事件转发订阅失败");
                    }
                }
            }

            let repo_for_bridge = repo.clone();
            let coordinator = Arc::new(ChannelCoordinator::new(
                repo,
                dispatcher.clone(),
                event_sink.clone(),
            ));

            let account_store = app.state::<crate::commands::AccountHandle>().store.clone();
            let wss_bridge = Arc::new(PythonWssBridge::new(
                app.state::<AppState>().lifecycle.clone(),
                coordinator.clone(),
                repo_for_bridge,
                app.state::<Arc<crate::config::ConfigStore>>()
                    .inner()
                    .clone(),
                account_store,
            ));
            coordinator.set_wss_bridge(wss_bridge.clone());
            app.manage(wss_bridge.clone());

            app.manage(coordinator.clone());

            crate::bootstrap::window::register_platform(
                app.handle(),
                &dispatcher,
                &coordinator,
                &wss_bridge,
            )?;
            lifecycle::on_platform_ready();
            lifecycle::spawn_startup_account_probe(app.handle());
            lifecycle::on_setup();
            Ok(())
        })
        .invoke_handler(crate::invoke_handler!())
        .build(context)?
        .run(move |app_handle, event| match event {
            RunEvent::Ready => lifecycle::on_run_ready(),
            RunEvent::Resumed => lifecycle::on_run_resumed(),
            RunEvent::ExitRequested { .. } => lifecycle::on_run_exit_requested(),
            RunEvent::Exit => {
                lifecycle::on_run_exit();
                let supervisor = app_handle.state::<AppState>().supervisor.clone();
                tauri::async_runtime::block_on(async move { supervisor.shutdown().await });
            }
            _ => {}
        });

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() -> tauri::Result<()> {
    use crate::infrastructure::license::UnlockedLicenseGate;
    run_with(Arc::new(UnlockedLicenseGate::new()))
}

/// 桌面 bin 入口：由 [`main`] 注入 License 闸门后启动。
pub fn run_with(license: Arc<dyn LicenseGate>) -> tauri::Result<()> {
    launch(tauri::generate_context!(), license)
}
