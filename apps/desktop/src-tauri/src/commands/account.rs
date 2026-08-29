//! 账号业务 IPC（CRUD / 扫码 / 登录探针）。

pub use crud::{
    account_create, account_delete, account_list, account_probe_login, account_set_status,
    account_update, AccountHandle,
};
pub use qr::{
    account_qr_cancel, account_qr_check, account_qr_start, AccountQrHandle, PostQrLoginHook,
};

mod crud {
    // 账号管理 Tauri commands — 多账号 CRUD + 状态切换。
    //
    // 壳层组合：`InMemoryAccountStore` → `crate::domain::account::AccountService`（校验 + 编排）。

    use crate::application::account::probe_account_session;
    use crate::bootstrap::state::AppState;
    use crate::commands::IpcResponse;
    use crate::domain::account::{AccountService, AccountStatus, AccountUpdate, XianyuAccount};
    use crate::infrastructure::database::stores::InMemoryAccountStore;
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
    ) -> crate::contracts::DingDaResult<IpcResponse<Vec<XianyuAccount>>> {
        let service = AccountService::new(state.store.as_ref());
        let result = service
            .list(owner_id)
            .map_err(crate::contracts::DingDaError::wrap)?;
        Ok(IpcResponse::ok(result))
    }

    /// 新建账号（含归属/唯一性校验）。
    #[tauri::command]
    pub fn account_create(
        state: State<'_, AccountHandle>,
        owner_id: i64,
        account: XianyuAccount,
    ) -> crate::contracts::DingDaResult<IpcResponse<XianyuAccount>> {
        let service = AccountService::new(state.store.as_ref());
        let result = service
            .create(owner_id, &account)
            .map_err(crate::contracts::DingDaError::wrap)?;
        Ok(IpcResponse::ok(result))
    }

    /// 更新账号（部分字段补丁）。
    #[tauri::command]
    pub fn account_update(
        state: State<'_, AccountHandle>,
        owner_id: i64,
        account_id: String,
        patch: AccountUpdate,
    ) -> crate::contracts::DingDaResult<IpcResponse<XianyuAccount>> {
        let service = AccountService::new(state.store.as_ref());
        let result = service
            .update(owner_id, &account_id, &patch)
            .map_err(crate::contracts::DingDaError::wrap)?;
        Ok(IpcResponse::ok(result))
    }

    /// 切换账号启用状态。
    #[tauri::command]
    pub fn account_set_status(
        state: State<'_, AccountHandle>,
        request: AccountStatusRequest,
    ) -> crate::contracts::DingDaResult<IpcResponse<()>> {
        let service = AccountService::new(state.store.as_ref());
        let status = AccountStatus::from_str(&request.status);
        service
            .set_status(request.owner_id, &request.account_id, status)
            .map_err(crate::contracts::DingDaError::wrap)?;
        Ok(IpcResponse::ok(()))
    }

    /// 删除账号（归属校验）。
    #[tauri::command]
    pub fn account_delete(
        state: State<'_, AccountHandle>,
        request: AccountDeleteRequest,
    ) -> crate::contracts::DingDaResult<IpcResponse<()>> {
        let service = AccountService::new(state.store.as_ref());
        service
            .delete(request.owner_id, &request.account_id)
            .map_err(crate::contracts::DingDaError::wrap)?;
        Ok(IpcResponse::ok(()))
    }

    /// 探测账号 Cookie 是否仍在线（1688 → 浏览器探针；闲鱼/小红书 → HTTP 刷新 token）。
    #[tauri::command]
    pub async fn account_probe_login(
        state: State<'_, AccountHandle>,
        app_state: State<'_, AppState>,
        request: AccountProbeRequest,
    ) -> crate::contracts::DingDaResult<IpcResponse<bool>> {
        let online = probe_account_session(
            state.store.as_ref(),
            app_state.lifecycle.as_ref(),
            request.owner_id,
            &request.account_id,
        )
        .await;
        Ok(IpcResponse::ok(online))
    }
}

mod qr {
    // 业务账号扫码登录 Tauri commands — 按平台（闲鱼 / 1688）扫码创建账号。
    //
    // 复用 sidecar 的 `channel_qr_*`；`platform` 决定登录页与 Cookie 落袋。
    // 落库成功后的平台后置逻辑（闲鱼建渠道 WS）由各平台 bootstrap 注入，
    // 本模块不做任何平台分支。
    //
    // 作者：Xiaoman
    // 创建时间：2026-08-20

    use crate::application::channel::dispatcher::ChannelDispatcher;
    use crate::bootstrap::state::AppState;
    use crate::commands::IpcResponse;
    use crate::contracts::{
        ChannelIpcQrCancelResponse, ChannelIpcQrCheckResponse, ChannelIpcQrStartResponse,
        ChannelSidecarQrCancelRequest, ChannelSidecarQrCheckRequest, ChannelSidecarQrStartRequest,
    };
    use crate::domain::account::{
        AccountService, AccountStore, AccountUpdate, LoginMethod, XianyuAccount,
    };
    use crate::infrastructure::database::account::normalize_account_platform;
    use crate::infrastructure::database::account_qr::account_from_cookies;
    use crate::infrastructure::database::stores::InMemoryAccountStore;
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
            )
                -> Pin<Box<dyn Future<Output = crate::contracts::DingDaResult<()>> + Send>>
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
            crate::infrastructure::sidecar::channel_login::qr_start(sidecar, sidecar_request)
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
            crate::infrastructure::sidecar::channel_login::qr_check(sidecar, sidecar_request)
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
            crate::infrastructure::sidecar::channel_login::qr_cancel(sidecar, sidecar_request)
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
}
