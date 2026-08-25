//! 业务账号 → 渠道连接桥接 Tauri commands。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use crate::cmd::AccountHandle;
use crate::cmd::IpcResponse;
use crate::contracts::contracts::ChannelAccount;
use crate::core::channel::dispatcher::ChannelDispatcher;
use crate::core::domain::account::{AccountService, AccountStore, AccountUpdate};
use crate::core::manager::python::routes::xianyu_user_profile::{self, UserProfileRequest};
use crate::core::manager::python::wss_bridge::{
    connect_channel, connection_state_for, disconnect_channel, PythonWssBridge,
};
use crate::feat::xianyu::persist::InMemoryAccountStore;
use crate::utils::state::AppState;
use serde::Deserialize;
use std::sync::Arc;
use tauri::State;

/// 连接请求。
#[derive(Debug, Deserialize)]
pub struct AccountConnectRequest {
    pub owner_id: i64,
    pub account_id: String,
}

/// 由业务账号构造渠道账号（credential = cookie 字符串）。
pub fn to_channel_account(
    _owner_id: i64,
    account: &crate::core::domain::account::XianyuAccount,
) -> ChannelAccount {
    ChannelAccount {
        id: account.account_id.clone(),
        kind: "xianyu".to_string(),
        name: if account.display_name.is_empty() {
            account.account_id.clone()
        } else {
            account.display_name.clone()
        },
        credential: account.cookie.clone(),
        enabled: account.is_active(),
    }
}

/// 连接成功后拉取闲鱼用户资料并写回业务账号（昵称 / 头像 / Cookie）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-19
///
/// # 参数
///
/// * `store` — 业务账号存储
/// * `owner_id` — 归属用户 id
/// * `account_id` — 账号标识
///
/// # 返回值
///
/// 成功返回 `()`；拉取或写入失败返回错误文案。
pub async fn sync_account_profile(
    lifecycle: &crate::core::manager::python::SidecarLifecycle,
    store: &InMemoryAccountStore,
    owner_id: i64,
    account_id: &str,
) -> crate::contracts::DingDaResult<()> {
    let account = store
        .get_account(owner_id, account_id)
        .map_err(crate::contracts::DingDaError::wrap)?
        .ok_or_else(|| format!("账号不存在: {account_id}"))?;
    if !account.has_cookie() {
        return Err("账号缺少 Cookie".into());
    }

    lifecycle
        .ensure_running()
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;
    let response = xianyu_user_profile::call(
        lifecycle.client(),
        UserProfileRequest {
            cookie: account.cookie.clone(),
        },
    )
    .await
    .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;
    if !response.ok {
        return Err(crate::contracts::DingDaError::wrap(
            response
                .message
                .unwrap_or_else(|| "用户资料拉取失败".to_string()),
        ));
    }
    let profile = response.profile.unwrap_or_default();
    let cookie = response.cookie.unwrap_or_else(|| account.cookie.clone());

    let service = AccountService::new(store);
    let patch = AccountUpdate {
        display_name: if profile.display_name.is_empty() {
            None
        } else {
            Some(profile.display_name.clone())
        },
        avatar_url: if profile.avatar_url.is_empty() {
            None
        } else {
            Some(profile.avatar_url.clone())
        },
        cookie: if cookie != account.cookie {
            Some(cookie)
        } else {
            None
        },
        ..Default::default()
    };

    if patch.display_name.is_none() && patch.avatar_url.is_none() && patch.cookie.is_none() {
        return Ok(());
    }

    service
        .update(owner_id, account_id, &patch)
        .map_err(crate::contracts::DingDaError::wrap)?;

    info!(
        account = %account_id,
        display_name = %profile.display_name,
        has_avatar = !profile.avatar_url.is_empty(),
        "闲鱼用户资料已同步"
    );
    Ok(())
}

/// 连接业务账号（建立渠道 websocket 设备监听）。
#[tauri::command]
pub async fn account_connect(
    state: State<'_, AppState>,
    accounts: State<'_, AccountHandle>,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    wss_bridge: State<'_, Arc<PythonWssBridge>>,
    request: AccountConnectRequest,
) -> crate::contracts::DingDaResult<IpcResponse<String>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    let account = accounts
        .store
        .get_account(request.owner_id, &request.account_id)
        .map_err(crate::contracts::DingDaError::wrap)?
        .ok_or_else(|| format!("账号不存在: {}", request.account_id))?;
    if !account.has_cookie() {
        return Err("账号缺少 Cookie，请先扫码登录".into());
    }

    let channel_account = to_channel_account(request.owner_id, &account);
    info!(account = %request.account_id, "开始连接闲鱼并绑定设备监听");
    connect_channel(wss_bridge.inner(), dispatcher.inner(), &channel_account)
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    if let Err(error) = sync_account_profile(
        state.lifecycle.as_ref(),
        &accounts.store,
        request.owner_id,
        &request.account_id,
    )
    .await
    {
        let text = error.to_string();
        // Session 过期不是「连接仍可用」：断开并让前端提示重新登录。
        if text.contains("FAIL_SYS_SESSION_EXPIRED")
            || text.contains("Session过期")
            || text.contains("SESSION_EXPIRED")
        {
            warn!(
                account = %request.account_id,
                %error,
                "登录态已过期，断开连接并提示重新登录"
            );
            let _ = disconnect_channel(
                wss_bridge.inner(),
                dispatcher.inner(),
                &request.account_id,
                "xianyu",
            )
            .await;
            return Err("登录态已过期，请重新扫码登录".into());
        }
        warn!(
            account = %request.account_id,
            %error,
            "拉取闲鱼用户资料失败，连接仍可用"
        );
    }

    Ok(IpcResponse::ok(
        connection_state_for(
            wss_bridge.inner(),
            dispatcher.inner(),
            &request.account_id,
            "xianyu",
        )
        .await
        .as_str()
        .to_string(),
    ))
}

/// 断开业务账号的渠道连接。
#[tauri::command]
pub async fn account_disconnect(
    state: State<'_, AppState>,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    wss_bridge: State<'_, Arc<PythonWssBridge>>,
    request: AccountConnectRequest,
) -> crate::contracts::DingDaResult<IpcResponse<()>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    info!(account = %request.account_id, "断开闲鱼连接");
    disconnect_channel(
        wss_bridge.inner(),
        dispatcher.inner(),
        &request.account_id,
        "xianyu",
    )
    .await
    .map_err(crate::contracts::DingDaError::wrap)?;
    Ok(IpcResponse::ok(()))
}

/// 查询业务账号的渠道连接状态。
#[tauri::command]
pub async fn account_connection_state(
    state: State<'_, AppState>,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    wss_bridge: State<'_, Arc<PythonWssBridge>>,
    request: AccountConnectRequest,
) -> crate::contracts::DingDaResult<IpcResponse<String>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    Ok(IpcResponse::ok(
        connection_state_for(
            wss_bridge.inner(),
            dispatcher.inner(),
            &request.account_id,
            "xianyu",
        )
        .await
        .as_str()
        .to_string(),
    ))
}

/// 手动触发浏览器滑块续期 — 薄转发 Python Sidecar，写回 Cookie 后重连。
#[tauri::command]
pub async fn account_cookie_renew(
    state: State<'_, AppState>,
    accounts: State<'_, AccountHandle>,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    wss_bridge: State<'_, Arc<PythonWssBridge>>,
    request: AccountConnectRequest,
) -> crate::contracts::DingDaResult<IpcResponse<String>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(crate::contracts::DingDaError::wrap)?;

    info!(account = %request.account_id, "手动触发闲鱼滑块续期（转发 Python）");
    let account = accounts
        .store
        .get_account(request.owner_id, &request.account_id)
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?
        .ok_or_else(|| {
            crate::contracts::DingDaError::validation(format!("账号不存在: {}", request.account_id))
        })?;
    if !account.has_cookie() {
        return Err(crate::contracts::DingDaError::validation("账号缺少 Cookie"));
    }
    let cookies = crate::core::store::cookies::parse_credential(&account.cookie);
    if cookies.is_empty() {
        return Err(crate::contracts::DingDaError::validation("Cookie 解析失败"));
    }

    state
        .lifecycle
        .ensure_running()
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

    let response = crate::core::manager::python::routes::channel_cookie_renew::call(
        state.lifecycle.client(),
        crate::contracts::contracts::ChannelSidecarCookieRenewRequest {
            account_id: request.account_id.clone(),
            cookies,
            punish_url: None,
            trace_id: Some(format!("manual-renew-{}", request.account_id)),
        },
    )
    .await
    .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

    if !response.ok {
        return Err(crate::contracts::DingDaError::wrap(
            response.detail.unwrap_or_else(|| "浏览器续期失败".into()),
        ));
    }
    let renewed = response
        .cookies
        .ok_or_else(|| crate::contracts::DingDaError::wrap("续期未返回 Cookie".to_string()))?;
    let credential = serde_json::to_string(&renewed).map_err(|error| error.to_string())?;
    let service = AccountService::new(accounts.store.as_ref());
    let updated = service
        .update(
            request.owner_id,
            &request.account_id,
            &AccountUpdate {
                cookie: Some(credential),
                ..Default::default()
            },
        )
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

    let channel_account = to_channel_account(request.owner_id, &updated);
    connect_channel(wss_bridge.as_ref(), dispatcher.as_ref(), &channel_account)
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

    Ok(IpcResponse::ok("滑块续期完成，已重连".to_string()))
}
