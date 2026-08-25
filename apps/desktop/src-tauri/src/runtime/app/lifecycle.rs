//! Tauri App 生命周期事件 → `[startup]` 观测日志。
//!
//! 只记录，不含任何运行控制（控制层在 `crate::runtime::supervisor`）；
//! 关闭/重启等决策由 `lib.rs` 调用 [`super::supervisor::RuntimeSupervisor`] 完成。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-24

use tauri::webview::PageLoadEvent;
use tauri::{Window, WindowEvent};

use super::startup;

/// 进程启动原点（`init_tracing()` 之后立刻调用一次）。
pub fn on_process_start() {
    startup::mark_start();
    startup::phase("rust.process.start");
}

/// AppState 装配完成。
pub fn on_state_ready() {
    startup::phase("rust.state.ready");
}

/// `setup` 完成（`lib.rs` setup 末尾调用）。
pub fn on_setup() {
    startup::phase("rust.setup.done");
}

/// `setup` 开始。
pub fn on_setup_begin() {
    startup::phase("rust.setup.begin");
}

/// 无窗口（`setup` 时没有可用 webview）。
pub fn on_window_none() {
    startup::phase("tauri.window.none");
}

/// 窗口就绪。
pub fn on_window_ready(label: &str, visible: bool) {
    startup::phase_detail(
        "tauri.window.ready",
        &format!("label={label} visible={visible}"),
    );
}

/// 插件环境（Camoufox / 插件目录）就绪。
pub fn on_plugin_env_ready() {
    startup::phase("rust.plugin_env.ready");
}

/// 业务库 / 账号 Handle 就绪。
pub fn on_business_ready() {
    startup::phase("rust.business.ready");
}

/// 渠道数据库就绪。
pub fn on_channel_db_ready() {
    startup::phase("rust.channel_db.ready");
}

/// 平台运行时（渠道协议 / 风控）就绪。
pub fn on_platform_ready() {
    startup::phase("rust.platform.ready");
}

/// 页面加载事件（仅首次）。
pub fn on_page_load(event: PageLoadEvent, url: &str) {
    match event {
        PageLoadEvent::Started => {
            startup::phase_once_detail("tauri.webview.load.start", &format!("url={url}"))
        }
        PageLoadEvent::Finished => {
            startup::phase_once_detail("tauri.webview.load.finish", &format!("url={url}"))
        }
    }
}

/// 窗口事件。
pub fn on_window_event(window: &Window, event: &WindowEvent) {
    match event {
        WindowEvent::Resized(_) => {
            startup::phase_once_detail("tauri.window.resized", &format!("label={}", window.label()))
        }
        WindowEvent::Focused(true) => {
            startup::phase_once_detail("tauri.window.focused", &format!("label={}", window.label()))
        }
        WindowEvent::Destroyed => startup::phase_detail(
            "tauri.window.destroyed",
            &format!("label={}", window.label()),
        ),
        _ => {}
    }
}

/// `RunEvent::Ready`。
pub fn on_run_ready() {
    startup::phase("tauri.run.ready");
}

/// `RunEvent::Resumed`（同名只打一次）。
pub fn on_run_resumed() {
    startup::phase_once("tauri.run.resumed");
}

/// `RunEvent::ExitRequested`。
pub fn on_run_exit_requested() {
    startup::phase("tauri.run.exit_requested");
}

/// `RunEvent::Exit` — 仅观测；运行时关闭由 `lib.rs` 调 supervisor。
pub fn on_run_exit() {
    startup::phase("tauri.run.exit");
    on_exit();
}

/// 应用退出。
pub fn on_exit() {
    info!(target: "dingda.lifecycle", "应用正在退出");
}
