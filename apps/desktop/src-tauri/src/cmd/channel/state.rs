//! 渠道通用 Tauri commands（状态 / 连接 / 发送）。
//!
//! 闲鱼专属历史 / 商品卡 / 渠道扫码见同目录 [`super::chat`]。

use crate::contracts::contracts::{
    ChannelConversation, ChannelIpcConnectResponse, ChannelIpcDisconnectResponse,
    ChannelIpcSendRequest, ChannelIpcSendResponse, ChannelIpcStateRequest, ChannelIpcStateResponse,
};
use std::sync::Arc;
use tauri::State;

use crate::cmd::IpcResponse;
use crate::contracts::DingDaResult;
use crate::core::channel::coordinator::ChannelCoordinator;
use crate::core::channel::dispatcher::ChannelDispatcher;
use crate::core::channel::ChannelRepo;
use crate::core::manager::python::wss_bridge::{
    connect_channel, connection_state_for, disconnect_channel, PythonWssBridge,
};

/// 读取渠道全量状态（账号/会话/消息/设置）。

#[tauri::command]
pub async fn channel_state_get(
    repo: State<'_, Arc<ChannelRepo>>,
) -> DingDaResult<IpcResponse<ChannelIpcStateResponse>> {
    let accounts = repo.list_accounts().map_err(|error| error.to_string())?;
    let conversations = repo
        .list_conversations()
        .map_err(|error| error.to_string())?;
    let messages = repo
        .list_all_messages()
        .map_err(|error| error.to_string())?;
    let settings = repo.get_settings().map_err(|error| error.to_string())?;
    Ok(IpcResponse::ok(ChannelIpcStateResponse {
        accounts,
        conversations,
        messages,
        settings,
    }))
}

/// 保存渠道配置（账号 + 设置）。

#[tauri::command]
pub async fn channel_state_set(
    repo: State<'_, Arc<ChannelRepo>>,
    request: ChannelIpcStateRequest,
) -> DingDaResult<IpcResponse<ChannelIpcStateResponse>> {
    for account in &request.accounts {
        repo.upsert_account(account)
            .map_err(|error| error.to_string())?;
    }
    repo.set_settings(&request.settings)
        .map_err(|error| error.to_string())?;
    channel_state_get(repo).await
}

/// 连接渠道账号。

#[tauri::command]
pub async fn channel_connect(
    state: tauri::State<'_, crate::utils::state::AppState>,
    coordinator: State<'_, Arc<ChannelCoordinator>>,
    repo: State<'_, Arc<ChannelRepo>>,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    wss_bridge: State<'_, Arc<PythonWssBridge>>,
    account_id: String,
) -> DingDaResult<IpcResponse<ChannelIpcConnectResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(|error| error.to_string())?;

    let accounts = repo.list_accounts().map_err(|error| error.to_string())?;
    let account = accounts
        .iter()
        .find(|account| account.id == account_id)
        .cloned()
        .ok_or_else(|| format!("账号不存在: {account_id}"))?;

    connect_channel(wss_bridge.inner(), dispatcher.inner(), &account)
        .await
        .map_err(|error| error.to_string())?;

    let _ = coordinator; // 协调器由 bridge / dispatcher 的 listener 绑定触发。

    let state = connection_state_for(
        wss_bridge.inner(),
        dispatcher.inner(),
        &account_id,
        &account.kind,
    )
    .await
    .as_str()
    .to_string();
    Ok(IpcResponse::ok(ChannelIpcConnectResponse {
        ok: true,
        state,
        detail: None,
    }))
}

/// 断开渠道账号。

#[tauri::command]
pub async fn channel_disconnect(
    state: tauri::State<'_, crate::utils::state::AppState>,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    wss_bridge: State<'_, Arc<PythonWssBridge>>,
    repo: State<'_, Arc<ChannelRepo>>,
    account_id: String,
) -> DingDaResult<IpcResponse<ChannelIpcDisconnectResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(|error| error.to_string())?;
    let kind = repo
        .list_accounts()
        .map_err(|error| error.to_string())?
        .into_iter()
        .find(|account| account.id == account_id)
        .map(|account| account.kind)
        .unwrap_or_else(|| "xianyu".to_string());
    disconnect_channel(wss_bridge.inner(), dispatcher.inner(), &account_id, &kind)
        .await
        .map_err(|error| error.to_string())?;
    Ok(IpcResponse::ok(ChannelIpcDisconnectResponse { ok: true }))
}

/// 人工发送消息。

#[tauri::command]
pub async fn channel_send(
    state: tauri::State<'_, crate::utils::state::AppState>,
    coordinator: State<'_, Arc<ChannelCoordinator>>,
    repo: State<'_, Arc<ChannelRepo>>,
    request: ChannelIpcSendRequest,
) -> DingDaResult<IpcResponse<ChannelIpcSendResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(|error| error.to_string())?;

    let conversation = repo
        .list_conversations()
        .map_err(|error| error.to_string())?
        .into_iter()
        .find(|conversation: &ChannelConversation| conversation.id == request.conversation_id)
        .ok_or_else(|| format!("会话不存在: {}", request.conversation_id))?;

    let message_id = coordinator
        .send_message(&conversation, &request.content)
        .await
        .map_err(|error| error.to_string())?;

    Ok(IpcResponse::ok(ChannelIpcSendResponse {
        ok: true,
        message_id,
        detail: None,
    }))
}
