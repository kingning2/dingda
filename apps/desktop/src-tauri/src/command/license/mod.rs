//! License 闸门 Tauri commands。
//!
//! 作者：coisini
//! 创建时间：2026-07-21

use crate::contracts::license::{LicenseActivateRequest, LicenseStatus};
use crate::contracts::DingDaResult;

use crate::command::IpcResponse;
use crate::runtime::app::startup;
use crate::state::AppState;

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
