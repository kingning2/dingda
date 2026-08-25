//! Tauri shell：组装 AppState、注册 IPC commands、启动 sidecar。
//!
//! 目录约定：
//! - [`shared`] — 三平台共用（IPC、渠道编排、Agent、License、日志）
//! - [`runtime`] — Runtime 层：按对象拆分生命周期（App / Python / Agent / Task）+ `RuntimeSupervisor` 协调
//! - [`platforms`] — 编译期平台壳层（`core` 两站共用；`xianyu` / `ali1688` 按 feature 裁剪）
//!
//! 生命周期职责：
//! - 观测：`runtime::app`（`[startup]` / 窗口 / 路由 / RunEvent 日志）
//! - 控制：`runtime::python` / `runtime::agent` / `runtime::tasks` / `runtime::supervisor`
//!
//! IPC 注册与平台条件编译收敛在 [`platforms::ipc`] / [`platforms::runtime`]；
//! 本文件仅负责 AppState 组装与 Tauri 生命周期编排。
//!
//! 根目录仅保留 `lib.rs` / `main.rs`。
//!
//! 作者：Xiaoman
//! 创建时间：2026-07-16

#[macro_use]
extern crate tracing;

mod platforms;
pub mod runtime;
mod shared;

// `#[timed]` 展开为 `crate::timing`；命令层历史路径 `crate::agent` / `crate::state` 等亦走此 re-export。
pub use shared::{config, logging, state, timing};

use infra::event::{EventBus, InMemoryEventBus};
use runtime::app::lifecycle;
use runtime::python::{
    RuntimeAgentSidecar, SidecarConfig, SidecarLifecycle, RUNTIME_ERROR_TOPIC,
    SIDECAR_RESTARTED_TOPIC,
};
use shared::channel::coordinator::ChannelCoordinator;
use shared::channel::dispatcher::ChannelDispatcher;
use shared::channel::ChannelRepo;
use shared::{build_license_gate, init_tracing, platform_initialization_script, AppState};
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
pub fn launch(context: tauri::Context<tauri::Wry>) -> tauri::Result<()> {
    init_tracing();
    lifecycle::on_process_start();

    let event_bus = Arc::new(InMemoryEventBus::new());
    let lifecycle = Arc::new(SidecarLifecycle::new(
        SidecarConfig::from_env(),
        event_bus.clone() as Arc<dyn EventBus>,
    ));
    let gateway = Arc::new(RuntimeAgentSidecar::new(lifecycle.client().clone()));
    let license = build_license_gate();
    let supervisor = Arc::new(runtime::RuntimeSupervisor::new(lifecycle.clone()));
    let app_state = AppState {
        lifecycle: lifecycle.clone(),
        gateway,
        license,
        event_bus,
        supervisor,
    };
    lifecycle::on_state_ready();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .append_invoke_initialization_script(platform_initialization_script())
        .manage(app_state)
        .on_page_load(|_webview, payload| {
            lifecycle::on_page_load(payload.event(), payload.url().as_str())
        })
        .on_window_event(|window, event| lifecycle::on_window_event(&window, &event))
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
            let config_store = Arc::new(shared::config::ConfigStore::new(
                config_dir.clone(),
                data_dir,
            ));
            shared::plugin_download::sync_camoufox_env(&config_store);
            lifecycle::on_plugin_env_ready();
            app.manage(config_store);
            let plugin_tracker = Arc::new(shared::plugin_download::PluginDownloadTracker::new());
            app.manage(plugin_tracker);

            platforms::core::bootstrap::register_business(app.handle(), &config_dir)?;
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

            let event_sink: Arc<dyn common::events::EventSink> =
                Arc::new(shared::TauriEventSink::new(app.handle().clone()));
            app.manage(event_sink.clone());

            {
                let forwarder = shared::BusToTauri::new(app.handle().clone());
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

            let risk_handler = platforms::runtime::build_risk_handler(
                app.handle(),
                &dispatcher,
                event_sink.clone(),
            );

            let coordinator = Arc::new(ChannelCoordinator::new(
                repo,
                dispatcher.clone(),
                event_sink,
                risk_handler,
            ));
            app.manage(coordinator.clone());

            platforms::runtime::register_platform(app.handle(), &dispatcher, &coordinator)?;
            lifecycle::on_platform_ready();

            let supervisor = app.state::<AppState>().supervisor.clone();
            tauri::async_runtime::spawn(async move { supervisor.start().await });
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
    launch(tauri::generate_context!())
}
