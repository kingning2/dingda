//! 内置插件 IPC — 列表、安装（下载）、卸载。
//!
//! OCR 语言包由主进程 HTTP 下载到 `{app_local_data}/plugins/ocr/tessdata/`，进度经
//! `plugin/progress` 事件推送前端。识别引擎不在本模块。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-19

use crate::contracts::contracts::{
    PluginIpcInstallRequest, PluginIpcInstallResponse, PluginIpcListResponse,
    PluginIpcUninstallRequest, PluginIpcUninstallResponse,
};
use crate::contracts::DingDaResult;
use std::sync::Arc;
use tauri::State;

use crate::cmd::IpcResponse;
use crate::config::ConfigStore;
use crate::utils::plugin_download::{
    install_plugin, plugin_list_with_status, sync_camoufox_env, PluginDownloadTracker,
};

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
