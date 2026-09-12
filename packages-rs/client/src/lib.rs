//! 叮答桌面壳入口。
//!
//! 职责：
//!     组装 Tauri Builder、登记 IPC、起停 Python Server、托盘与窗口。
//!
//! 设计说明：
//!     - 具体能力已拆到 `packages-rs/` 下的成员包，本包只做编排
//!     - 包边界与依赖方向见 `src/README.md`
//!     - 路径基准与 dev 判定必须由本包注入（见 `run()` 开头），成员包自己算不出来

mod commands;

use std::path::{Path, PathBuf};
use std::sync::Arc;

use common::platform::platform_initialization_script;
use common::{logging, paths};
use python::{PythonConfig, PythonLifecycle};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, RunEvent, WindowEvent};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // 三个开关都必须早于任何 resolve_* / is_packaged_install。
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    paths::set_app_root(manifest_dir.clone());
    paths::set_repo_root(repo_root_from_manifest_dir(&manifest_dir));
    paths::set_dev_mode(cfg!(dev));
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .append_invoke_initialization_script(platform_initialization_script())
        .setup(|app| {
            let server_dir = paths::ensure_server_workdir(app.handle());
            let uv_bin = paths::resolve_uv_bin(app.handle());
            let runtime_env = python::desktop_runtime_env(app.handle(), &server_dir);
            let mut config = PythonConfig::from_env();
            config.server_dir = server_dir;
            config.uv_bin = uv_bin;
            config.extra_env = runtime_env;
            // 首次 uv sync 可能较久（国内镜像拉依赖）
            if paths::is_packaged_install() {
                config.startup_timeout = std::time::Duration::from_secs(600);
                config.use_uv = true;
            }
            let runtime = Arc::new(PythonLifecycle::new(config));
            let runtime_for_bg = Arc::clone(&runtime);
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(error) = runtime_for_bg.start_background(app_handle).await {
                    logging::log(
                        logging::Scope::Shell,
                        "python server background start failed",
                        Some(&error.to_string()),
                    );
                }
            });
            app.manage(runtime);
            setup_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::api::get_api_base_url,
            commands::api::get_server_status,
            commands::agent_runtime::list_agent_runtimes_command,
            commands::agent_runtime::list_agent_registry_command,
            commands::agent_runtime::probe_agent_runtime,
            commands::agent_runtime::login_agent_runtime,
            commands::agent_runtime::download_agent_runtime,
            commands::dialog::pick_file,
            commands::dialog::pick_folder,
            commands::frontend::log_frontend_error,
            commands::os::show_in_folder,
        ])
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                let app = window.app_handle().clone();
                stop_python_server(&app);
                app.exit(0);
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if matches!(event, RunEvent::Exit) {
                stop_python_server(app);
            }
        });
}

fn setup_tray(app: &AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "tray-show", "显示窗口", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "tray-quit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;

    let _tray = TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .tooltip("DingDa v2")
        .on_menu_event(|app, event| match event.id.as_ref() {
            "tray-show" => show_main_window(app),
            "tray-quit" => {
                stop_python_server(app);
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        })
        .build(app)?;

    Ok(())
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn stop_python_server(app: &AppHandle) {
    let Some(runtime) = app.try_state::<Arc<PythonLifecycle>>() else {
        return;
    };
    tauri::async_runtime::block_on(async {
        if let Err(error) = runtime.stop().await {
            logging::log(
                logging::Scope::Shell,
                "failed to stop python server",
                Some(&error.to_string()),
            );
        }
    });
    let _ = app.emit("server-stopped", ());
}

/// 由壳包目录（`packages-rs/client`）反推仓库根。
///
/// 壳固定落在 `packages-rs/<pkg>`，故仓库根就是它的上两级；`server/` 以仓库根
/// 为基准（见 `common::paths::resolve_server_dir`）。
///
/// 之所以抽成独立函数而不是内联：这段推导没有任何类型保护，目录层级一旦变动
/// （例如壳被挪到 `packages-rs/<scope>/client`），`resolve_server_dir()` 会静默
/// 指向一个不存在的目录，直到 Python 启动失败才暴露。必须由测试兜住。
fn repo_root_from_manifest_dir(manifest_dir: &Path) -> PathBuf {
    manifest_dir
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or_else(|| manifest_dir.to_path_buf())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 壳包目录 → 仓库根 的两级上溯必须落到真实仓库根上。
    ///
    /// 这是本次 Rust workspace 拆分里最容易静默失败的一环，故断言到「推导结果
    /// 下确实存在 server/ 与 packages-rs/」为止，而不只比较字符串。
    #[test]
    fn repo_root_from_manifest_dir_points_at_real_repo() {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo_root = repo_root_from_manifest_dir(&manifest_dir);

        assert_eq!(
            manifest_dir.file_name().and_then(|name| name.to_str()),
            Some("client"),
            "壳包目录应位于 packages-rs/client，实际为 {}",
            manifest_dir.display()
        );
        assert_eq!(
            manifest_dir.parent().and_then(|dir| dir.file_name()),
            Some(std::ffi::OsStr::new("packages-rs")),
            "壳包目录的上一级应为 packages-rs，实际为 {}",
            manifest_dir.display()
        );
        assert!(
            repo_root.join("server").join("src").is_dir(),
            "推导出的仓库根下没有 server/src：{}",
            repo_root.display()
        );
        assert!(
            repo_root.join("packages-rs").is_dir(),
            "推导出的仓库根下没有 packages-rs：{}",
            repo_root.display()
        );
    }

    /// 层级不足时退化为原路径，不得返回一个更上层的目录。
    #[test]
    fn repo_root_from_manifest_dir_falls_back_when_too_shallow() {
        assert_eq!(
            repo_root_from_manifest_dir(Path::new("only-one-level")),
            PathBuf::from("only-one-level")
        );
        assert_eq!(repo_root_from_manifest_dir(Path::new("")), PathBuf::new());
    }
}
