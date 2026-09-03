mod agent;
mod commands;
mod paths;
mod platform;
mod python;
mod runtime;

use std::sync::Arc;

use platform::platform_initialization_script;
use python::{PythonConfig, PythonLifecycle};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, RunEvent, WindowEvent};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .append_invoke_initialization_script(platform_initialization_script())
        .setup(|app| {
            let runtime = Arc::new(PythonLifecycle::new(PythonConfig::from_env()));
            let runtime_for_bg = Arc::clone(&runtime);
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(error) = runtime_for_bg.start_background(app_handle).await {
                    eprintln!("[shell] python backend background start failed: {error}");
                }
            });
            app.manage(runtime);
            setup_tray(app.handle())?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::api::get_api_base_url,
            commands::api::get_backend_status,
            commands::agent_runtime::list_agent_runtimes_command,
            commands::agent_runtime::probe_agent_runtime,
            commands::agent_runtime::login_agent_runtime,
            commands::agent_runtime::launch_agent_runtime,
            commands::agent_runtime::cancel_agent_runtime,
            commands::dialog::pick_file,
            commands::dialog::pick_folder,
            commands::frontend::log_frontend_error,
            commands::os::show_in_folder,
        ])
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::CloseRequested { .. }) {
                let app = window.app_handle().clone();
                stop_python_backend(&app);
                app.exit(0);
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app, event| {
            if matches!(event, RunEvent::Exit) {
                stop_python_backend(app);
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
                stop_python_backend(app);
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

fn stop_python_backend(app: &AppHandle) {
    let Some(runtime) = app.try_state::<Arc<PythonLifecycle>>() else {
        return;
    };
    tauri::async_runtime::block_on(async {
        if let Err(error) = runtime.stop().await {
            eprintln!("[shell] failed to stop python backend: {error}");
        }
    });
    let _ = app.emit("backend-stopped", ());
}
