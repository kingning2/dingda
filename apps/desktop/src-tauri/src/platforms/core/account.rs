//! 账号管理 Tauri commands — 多账号 CRUD + 状态切换。
//!
//! 壳层组合：`InMemoryAccountStore` → `platform::domain::account::AccountService`（校验 + 编排）。

use crate::shared::ipc::IpcResponse;
use crate::shared::state::AppState;
use common;
use common::contracts::ChannelSidecarLoginProbeRequest;
use platform::domain::account::{
    AccountService, AccountStatus, AccountStore, AccountUpdate, XianyuAccount,
};
use platform::shared::cookies::parse_credential;
use platform::shared::resolve_account_platform;
use platform::shared::stores::InMemoryAccountStore;
use serde::Deserialize;
use std::sync::Arc;
use tauri::State;

/// 账号状态变更入参。
#[derive(Debug, Deserialize)]
pub struct AccountStatusRequest {
    pub owner_id: i64,
    pub account_id: String,
    pub status: String,
}

/// 账号删除入参。
#[derive(Debug, Deserialize)]
pub struct AccountDeleteRequest {
    pub owner_id: i64,
    pub account_id: String,
}

/// 账号探针入参（owner + account_id）。
#[derive(Debug, Deserialize)]
pub struct AccountProbeRequest {
    pub owner_id: i64,
    pub account_id: String,
}

/// 账号服务句柄（setup 时注册到 Tauri 状态）。
pub struct AccountHandle {
    pub store: Arc<InMemoryAccountStore>,
}

/// 查询账号列表。
#[tauri::command]
pub fn account_list(
    state: State<'_, AccountHandle>,
    owner_id: i64,
) -> common::DingDaResult<IpcResponse<Vec<XianyuAccount>>> {
    let service = AccountService::new(state.store.as_ref());
    let result = service.list(owner_id).map_err(common::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

/// 新建账号（含归属/唯一性校验）。
#[tauri::command]
pub fn account_create(
    state: State<'_, AccountHandle>,
    owner_id: i64,
    account: XianyuAccount,
) -> common::DingDaResult<IpcResponse<XianyuAccount>> {
    let service = AccountService::new(state.store.as_ref());
    let result = service
        .create(owner_id, &account)
        .map_err(common::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

/// 更新账号（部分字段补丁）。
#[tauri::command]
pub fn account_update(
    state: State<'_, AccountHandle>,
    owner_id: i64,
    account_id: String,
    patch: AccountUpdate,
) -> common::DingDaResult<IpcResponse<XianyuAccount>> {
    let service = AccountService::new(state.store.as_ref());
    let result = service
        .update(owner_id, &account_id, &patch)
        .map_err(common::DingDaError::wrap)?;
    Ok(IpcResponse::ok(result))
}

/// 切换账号启用状态。
#[tauri::command]
pub fn account_set_status(
    state: State<'_, AccountHandle>,
    request: AccountStatusRequest,
) -> common::DingDaResult<IpcResponse<()>> {
    let service = AccountService::new(state.store.as_ref());
    let status = AccountStatus::from_str(&request.status);
    service
        .set_status(request.owner_id, &request.account_id, status)
        .map_err(common::DingDaError::wrap)?;
    Ok(IpcResponse::ok(()))
}

/// 删除账号（归属校验）。
#[tauri::command]
pub fn account_delete(
    state: State<'_, AccountHandle>,
    request: AccountDeleteRequest,
) -> common::DingDaResult<IpcResponse<()>> {
    let service = AccountService::new(state.store.as_ref());
    service
        .delete(request.owner_id, &request.account_id)
        .map_err(common::DingDaError::wrap)?;
    Ok(IpcResponse::ok(()))
}

/// 探测账号 Cookie 是否仍在线（1688 → sidecar Playwright；闲鱼 → mtop 用户资料）。
#[tauri::command]
pub async fn account_probe_login(
    state: State<'_, AccountHandle>,
    app_state: State<'_, AppState>,
    request: AccountProbeRequest,
) -> common::DingDaResult<IpcResponse<bool>> {
    let account = state
        .store
        .get_account(request.owner_id, &request.account_id)
        .map_err(common::DingDaError::wrap)?
        .ok_or_else(|| format!("账号不存在: {}", request.account_id))?;
    let platform = resolve_account_platform(&account.account_id, &account.platform);

    tracing::info!(
        target: "dingda.platform.login_probe",
        account_id = %request.account_id,
        platform,
        stored_platform = %account.platform,
        has_cookie = account.has_cookie(),
        unb = %account.unb,
        "账号登录探针开始"
    );

    if !account.has_cookie() {
        tracing::info!(
            target: "dingda.platform.login_probe",
            account_id = %request.account_id,
            reason = "empty_cookie",
            "账号登录探针跳过"
        );
        return Ok(IpcResponse::ok(false));
    }

    let ok = if platform == "ali1688" {
        let cookies = parse_credential(&account.cookie);
        if cookies.is_empty() {
            tracing::info!(
                target: "dingda.platform.login_probe",
                account_id = %request.account_id,
                reason = "unparseable_cookie",
                "1688 登录探针跳过"
            );
            false
        } else {
            let sidecar_request = ChannelSidecarLoginProbeRequest {
                account_id: request.account_id.clone(),
                cookies,
                headed: Some(false),
                platform: Some("ali1688".to_string()),
                trace_id: Some(format!("ali1688-login-probe-{}", request.account_id)),
            };
            let sidecar = app_state.lifecycle.client();
            match crate::runtime::python::routes::channel_login_probe::call(
                sidecar,
                sidecar_request,
            )
            .await
            {
                Ok(response) => {
                    tracing::info!(
                        target: "dingda.platform.ali1688.login_probe",
                        account_id = %request.account_id,
                        online = response.online,
                        status = %response.status,
                        detail = response.detail.as_deref().unwrap_or(""),
                        "1688 Playwright 登录探针完成"
                    );
                    response.ok && response.online
                }
                Err(error) => {
                    tracing::info!(
                        target: "dingda.platform.ali1688.login_probe",
                        account_id = %request.account_id,
                        error = %error,
                        "1688 Playwright 登录探针失败，视为离线"
                    );
                    false
                }
            }
        }
    } else {
        platform::xianyu::fetch_user_profile(&account.cookie)
            .await
            .is_ok()
    };

    tracing::info!(
        target: "dingda.platform.login_probe",
        account_id = %request.account_id,
        platform,
        online = ok,
        "账号登录探针完成"
    );
    Ok(IpcResponse::ok(ok))
}
