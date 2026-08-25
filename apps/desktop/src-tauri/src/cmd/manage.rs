//! 产品管理 IPC — License 授权 / 内置插件。

use crate::cmd::IpcResponse;
use crate::config::ConfigStore;
use crate::contracts::contracts::{
    PluginIpcInstallRequest, PluginIpcInstallResponse, PluginIpcListResponse,
    PluginIpcUninstallRequest, PluginIpcUninstallResponse,
};
use crate::contracts::license::{LicenseActivateRequest, LicenseStatus};
use crate::contracts::DingDaResult;
use crate::core::manager::app::startup;
use crate::state::AppState;
use crate::utils::plugin_download::{
    install_plugin, plugin_list_with_status, sync_camoufox_env, PluginDownloadTracker,
};
use std::sync::Arc;
use tauri::State;

/// 查询当前授权状态的 IPC。
///
/// 作者：coisini
/// 创建时间：2026-07-16
///
/// # 参数
/// - `state` — 应用共享状态
///
/// # 返回值
/// 当前 [`LicenseStatus`]。
#[tauri::command]
pub async fn license_status(
    state: tauri::State<'_, AppState>,
) -> DingDaResult<IpcResponse<LicenseStatus>> {
    let within_startup = startup::elapsed_ms() < 15_000;
    if within_startup {
        startup::phase("license.status.begin");
    }
    let status = state
        .license
        .status()
        .await
        .map_err(|error| error.to_string())?;
    if within_startup {
        startup::phase("license.status.end");
    }
    Ok(IpcResponse::ok(status))
}

/// 读取本机机器码的 IPC。
///
/// 作者：coisini
/// 创建时间：2026-07-16
///
/// # 参数
/// - `state` — 应用共享状态
///
/// # 返回值
/// 本机机器码字符串。
#[tauri::command]
pub async fn license_machine_code(
    state: tauri::State<'_, AppState>,
) -> DingDaResult<IpcResponse<String>> {
    Ok(IpcResponse::ok(
        state
            .license
            .machine_code()
            .await
            .map_err(|error| error.to_string())?,
    ))
}

/// 提交激活请求的 IPC。
///
/// 作者：coisini
/// 创建时间：2026-07-16
///
/// # 参数
/// - `state` — 应用共享状态
/// - `request` — 激活码或 license key
///
/// # 返回值
/// 激活后的 [`LicenseStatus`]。
#[tauri::command]
pub async fn license_activate(
    state: tauri::State<'_, AppState>,
    request: LicenseActivateRequest,
) -> DingDaResult<IpcResponse<LicenseStatus>> {
    Ok(IpcResponse::ok(
        state
            .license
            .activate(request)
            .await
            .map_err(|error| error.to_string())?,
    ))
}

/// 列出内置插件及安装状态。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
///
/// # 参数
///
/// * `state` — 应用配置存储
/// * `tracker` — 下载中状态
///
/// # 返回值
///
/// 插件列表（含 downloading）。
#[tauri::command]
pub async fn plugin_list(
    state: State<'_, Arc<ConfigStore>>,
    tracker: State<'_, Arc<PluginDownloadTracker>>,
) -> DingDaResult<IpcResponse<PluginIpcListResponse>> {
    Ok(IpcResponse::ok(PluginIpcListResponse {
        items: plugin_list_with_status(&state, &tracker).await,
    }))
}

/// 下载并安装指定插件到本应用 `plugins/{id}/`。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
///
/// # 参数
///
/// * `app` — 进度事件发射器
/// * `state` — 应用配置存储
/// * `tracker` — 下载互斥
/// * `request` — 含 `plugin_id`
///
/// # 返回值
///
/// 安装后的插件条目。
#[tauri::command]
pub async fn plugin_install(
    app: tauri::AppHandle,
    state: State<'_, Arc<ConfigStore>>,
    tracker: State<'_, Arc<PluginDownloadTracker>>,
    request: PluginIpcInstallRequest,
) -> DingDaResult<IpcResponse<PluginIpcInstallResponse>> {
    let item = install_plugin(&app, &state, &tracker, &request.plugin_id).await?;
    Ok(IpcResponse::ok(PluginIpcInstallResponse { item }))
}

/// 卸载指定插件的本地文件（仅本应用 `plugins/{id}/`）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
///
/// # 参数
///
/// * `state` — 应用配置存储
/// * `request` — 含 `plugin_id`
///
/// # 返回值
///
/// 卸载后的插件条目。
#[tauri::command]
pub async fn plugin_uninstall(
    state: State<'_, Arc<ConfigStore>>,
    request: PluginIpcUninstallRequest,
) -> DingDaResult<IpcResponse<PluginIpcUninstallResponse>> {
    let item = state.plugin_uninstall(request.plugin_id.trim())?;
    sync_camoufox_env(&state);
    Ok(IpcResponse::ok(PluginIpcUninstallResponse { item }))
}
