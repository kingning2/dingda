//! 业务账号扫码登录 Tauri commands — 按平台（闲鱼 / 1688）扫码创建账号。
//!
//! 复用 sidecar 的 `channel_qr_*`；`platform` 决定登录页与 Cookie 落袋。
//! 落库成功后的平台后置逻辑（闲鱼建渠道 WS）由各平台 bootstrap 注入，
//! 本模块不做任何平台分支。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-20

use crate::cmd::IpcResponse;
use crate::contracts::contracts::{
    ChannelIpcQrCancelResponse, ChannelIpcQrCheckResponse, ChannelIpcQrStartResponse,
    ChannelSidecarQrCancelRequest, ChannelSidecarQrCheckRequest, ChannelSidecarQrStartRequest,
};
use crate::core::channel::dispatcher::ChannelDispatcher;
use crate::core::domain::account::{
    AccountService, AccountStore, AccountUpdate, LoginMethod, XianyuAccount,
};
use crate::core::store::account::normalize_account_platform;
use crate::core::store::account_qr::account_from_cookies;
use crate::core::store::stores::InMemoryAccountStore;
use crate::utils::state::AppState;
use serde::Deserialize;
use std::future::Future;
use std::pin::Pin;
use std::sync::{Arc, RwLock};
use tauri::{AppHandle, Manager, State};
use tracing::info;

/// 扫码落库成功后的平台后置逻辑（闲鱼自动建渠道 WS 等）。
///
/// 由各平台 bootstrap 注入：`xianyu` 传连接钩子，`ali1688` 传 `None`。
///
/// 参数依次为调度器、业务账号存储、归属用户 id、已落库的业务账号；
/// 返回统一的业务结果，失败会上抛给调用方。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-22
pub type PostQrLoginHook = Arc<
    dyn Fn(
            Arc<ChannelDispatcher>,
            Arc<InMemoryAccountStore>,
            i64,
            XianyuAccount,
        ) -> Pin<Box<dyn Future<Output = crate::contracts::DingDaResult<()>> + Send>>
        + Send
        + Sync,
>;

/// 业务账号扫码服务句柄（setup 时注册到 Tauri 状态）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
pub struct AccountQrHandle {
    pub store: Arc<InMemoryAccountStore>,
    /// 扫码成功后的平台后置逻辑；`None` 表示无后置动作（1688 仅落库）。
    /// 由两站共用 `core::bootstrap` 初始化为 `None`，闲鱼 bootstrap 启动时写入。
    pub post_login: RwLock<Option<PostQrLoginHook>>,
}

/// 扫码启动入参。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[derive(Debug, Deserialize)]
pub struct AccountQrStartRequest {
    /// 展示名称（可选）。
    #[serde(default)]
    pub name: Option<String>,
    /// 平台：`xianyu` / `ali1688`；缺省闲鱼。
    #[serde(default)]
    pub platform: Option<String>,
}

/// 扫码轮询入参（带平台，避免与会话平台不匹配）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-22
#[derive(Debug, Deserialize)]
pub struct AccountQrSessionRequest {
    pub session_id: String,
    #[serde(default)]
    pub platform: Option<String>,
}

/// 启动业务账号扫码登录。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn account_qr_start(
    state: State<'_, AppState>,
    request: AccountQrStartRequest,
) -> crate::contracts::DingDaResult<IpcResponse<ChannelIpcQrStartResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    let platform = normalize_account_platform(request.platform.as_deref().unwrap_or("xianyu"));
    let sidecar_request = ChannelSidecarQrStartRequest {
        account_id: String::new(),
        trace_id: Some(
            request
                .name
                .clone()
                .unwrap_or_else(|| format!("account-qr-{platform}")),
        ),
        platform: Some(platform.to_string()),
    };
    let sidecar = state.lifecycle.client();
    let response =
        crate::core::manager::python::routes::channel_qr_start::call(sidecar, sidecar_request)
            .await
            .map_err(crate::contracts::DingDaError::wrap)?;

    Ok(IpcResponse::ok(ChannelIpcQrStartResponse {
        ok: response.ok,
        status: response.status,
        session_id: response.session_id,
        qr_base64: response.qr_base64,
        detail: response.detail,
    }))
}

/// 轮询扫码状态；成功后按平台落库。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn account_qr_check(
    state: State<'_, AppState>,
    app: AppHandle,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    request: AccountQrSessionRequest,
) -> crate::contracts::DingDaResult<IpcResponse<ChannelIpcQrCheckResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    let platform = normalize_account_platform(request.platform.as_deref().unwrap_or("xianyu"));
    let sidecar_request = ChannelSidecarQrCheckRequest {
        session_id: request.session_id.clone(),
        trace_id: Some(request.session_id.clone()),
        platform: Some(platform.to_string()),
    };
    let sidecar = state.lifecycle.client();
    let response =
        crate::core::manager::python::routes::channel_qr_check::call(sidecar, sidecar_request)
            .await
            .map_err(crate::contracts::DingDaError::wrap)?;

    if response.status == "success" {
        if let Some(cookies) = response.cookies.clone() {
            let account = account_from_cookies(platform, &cookies);
            let handle = app.state::<AccountQrHandle>();
            let service = AccountService::new(handle.store.as_ref());

            match handle.store.get_account(1, &account.account_id) {
                Ok(Some(_)) => {
                    service
                        .update(
                            1,
                            &account.account_id,
                            &AccountUpdate {
                                cookie: Some(account.cookie.clone()),
                                cookie_1688: Some(account.cookie_1688.clone()),
                                unb: Some(account.unb.clone()),
                                platform: Some(platform.to_string()),
                                login_method: Some(LoginMethod::Qr),
                                last_login_at: Some(now_string()),
                                ..Default::default()
                            },
                        )
                        .map_err(crate::contracts::DingDaError::wrap)?;
                }
                _ => {
                    service
                        .create(1, &account)
                        .map_err(crate::contracts::DingDaError::wrap)?;
                }
            }

            info!(
                account = %account.account_id,
                platform,
                "扫码成功，账号已落库"
            );

            // 平台后置逻辑（闲鱼自动建渠道 WS / 拉资料）由 bootstrap 写入；
            // 1688 无后置，`post_login` 为 `None`，此处不执行。
            let post_login = handle
                .post_login
                .read()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .clone();
            if let Some(hook) = post_login {
                hook(dispatcher.inner().clone(), handle.store.clone(), 1, account)
                    .await
                    .map_err(crate::contracts::DingDaError::wrap)?;
            }
        }
    }

    Ok(IpcResponse::ok(ChannelIpcQrCheckResponse {
        ok: response.ok,
        status: response.status,
        session_id: response.session_id,
        cookies: response.cookies,
        detail: response.detail,
        qr_base64: response.qr_base64,
    }))
}

/// 取消业务账号扫码登录。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn account_qr_cancel(
    state: State<'_, AppState>,
    request: AccountQrSessionRequest,
) -> crate::contracts::DingDaResult<IpcResponse<ChannelIpcQrCancelResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    let platform = normalize_account_platform(request.platform.as_deref().unwrap_or("xianyu"));
    let sidecar_request = ChannelSidecarQrCancelRequest {
        session_id: request.session_id.clone(),
        trace_id: Some(request.session_id.clone()),
        platform: Some(platform.to_string()),
    };
    let sidecar = state.lifecycle.client();
    let response =
        crate::core::manager::python::routes::channel_qr_cancel::call(sidecar, sidecar_request)
            .await
            .map_err(crate::contracts::DingDaError::wrap)?;

    Ok(IpcResponse::ok(ChannelIpcQrCancelResponse {
        ok: response.ok,
        detail: response.detail,
    }))
}

fn now_string() -> String {
    use chrono::Utc;
    Utc::now().format("%Y-%m-%d %H:%M:%S").to_string()
}
