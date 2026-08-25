//! 闲鱼专属渠道 IPC — 消息历史 / 商品卡 / 渠道扫码登录。
//!
//! 通用渠道命令（状态 / 连接 / 发送）留在 `shared::ipc::channel`；
//! 本模块收纳依赖 `platform_xianyu` 的闲鱼专属命令：
//! 历史拉取（`cookies::my_id` 判断方向）、商品卡 `headinfo`、渠道扫码（硬编码 `xianyu`）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-22

use common::contracts::{
    ChannelIpcQrCancelRequest, ChannelIpcQrCancelResponse, ChannelIpcQrCheckRequest,
    ChannelIpcQrCheckResponse, ChannelIpcQrStartRequest, ChannelIpcQrStartResponse, ChannelMessage,
    ChannelSidecarQrCancelRequest, ChannelSidecarQrCheckRequest, ChannelSidecarQrStartRequest,
};
use common::events::{emit, AppEvent, ChannelMessageEvent, EventSink};
use common::{DingDaError, DingDaResult};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};
use tauri::State;
use tracing::{info, warn};
use uuid::Uuid;

use crate::shared::channel::dispatcher::ChannelDispatcher;
use crate::shared::channel::ChannelRepo;
use crate::shared::ipc::IpcResponse;

/// QR 扫码会话的登录目标：绑定已有账号，或登录成功后自动创建。
enum QrTarget {
    Existing(String),
    Pending { kind: String, name: String },
}

/// QR 扫码会话 → 登录目标映射（qr_start 登记，qr_check 消费）。
fn qr_account_map() -> &'static Mutex<HashMap<String, QrTarget>> {
    static MAP: OnceLock<Mutex<HashMap<String, QrTarget>>> = OnceLock::new();
    MAP.get_or_init(|| Mutex::new(HashMap::new()))
}

/// 拉取会话完整消息历史（写入本地并推送；返回新插入条数）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn channel_fetch_history(
    state: tauri::State<'_, crate::shared::state::AppState>,
    repo: State<'_, Arc<ChannelRepo>>,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    event_sink: State<'_, Arc<dyn EventSink>>,
    conversation_id: String,
) -> DingDaResult<IpcResponse<u32>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(|error| error.to_string())?;

    let conversation = repo
        .find_conversation_by_id(&conversation_id)
        .map_err(|error| DingDaError::store(error.to_string()))?
        .ok_or_else(|| DingDaError::not_found("conversation", &conversation_id))?;

    // 账号自身 goofish id（unb），用于判断消息方向（我发的 → out）。
    let my_unb = repo
        .list_accounts()
        .map_err(|error| DingDaError::store(error.to_string()))?
        .into_iter()
        .find(|account| account.id == conversation.account_id)
        .and_then(|account| {
            let cookie_list = platform::shared::cookies::parse_credential(&account.credential);
            platform::shared::cookies::my_id(&cookie_list)
        });

    let cid = conversation
        .cid
        .clone()
        .unwrap_or_else(|| conversation.peer_id.clone());
    let history = dispatcher
        .fetch_history(&conversation.account_id, &cid)
        .await?;

    let existing = repo
        .list_messages(&conversation.id)
        .map_err(|error| DingDaError::store(error.to_string()))?;

    let mut inserted = 0u32;
    for (index, item) in history.into_iter().enumerate() {
        let outbound = my_unb
            .as_ref()
            .is_some_and(|unb| item.sender_user_id == *unb);
        let message = ChannelMessage {
            id: format!("h-{}-{}-{}", conversation.id, item.created_at_ms, index),
            conversation_id: conversation.id.clone(),
            direction: if outbound {
                "out".to_string()
            } else {
                "in".to_string()
            },
            sender: if outbound {
                "human".to_string()
            } else {
                "customer".to_string()
            },
            content: item.content,
            created_at: item.created_at_ms.to_string(),
        };
        // 去重：同会话同时间同内容的已存在则跳过（WS 推送与历史可能重复）。
        if existing
            .iter()
            .any(|m| m.created_at == message.created_at && m.content == message.content)
        {
            continue;
        }
        repo.insert_message(&message)
            .map_err(|error| DingDaError::store(error.to_string()))?;
        emit_message(event_sink.as_ref(), &conversation.account_id, message);
        inserted += 1;
    }
    info!(
        conversation_id = %conversation_id,
        inserted,
        "会话消息历史已同步"
    );
    Ok(IpcResponse::ok(inserted))
}

/// 拉取会话关联商品卡信息（`message.headinfo`，GET）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn channel_product_headinfo(
    state: tauri::State<'_, crate::shared::state::AppState>,
    repo: State<'_, Arc<ChannelRepo>>,
    conversation_id: String,
) -> DingDaResult<IpcResponse<Value>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(|error| error.to_string())?;

    let conversation = repo
        .find_conversation_by_id(&conversation_id)
        .map_err(|error| DingDaError::store(error.to_string()))?
        .ok_or_else(|| DingDaError::not_found("conversation", &conversation_id))?;
    let account = repo
        .list_accounts()
        .map_err(|error| DingDaError::store(error.to_string()))?
        .into_iter()
        .find(|account| account.id == conversation.account_id)
        .ok_or_else(|| DingDaError::not_found("account", &conversation.account_id))?;
    let cookie_str = platform::shared::cookies::cookies_to_string(
        &platform::shared::cookies::parse_credential(&account.credential),
    );
    let item_id = conversation.item_id.unwrap_or_default();
    let session_id = conversation
        .cid
        .clone()
        .unwrap_or_else(|| conversation.peer_id.clone());
    let data = platform::xianyu::fetch_message_headinfo(&cookie_str, &session_id, &item_id).await?;
    Ok(IpcResponse::ok(data))
}

/// 启动扫码登录：调 Python Playwright 打开登录页，截图二维码。
/// 无账号（account_id 为空或不存在）时标记为登录成功后自动创建。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn channel_qr_start(
    state: tauri::State<'_, crate::shared::state::AppState>,
    repo: State<'_, Arc<ChannelRepo>>,
    request: ChannelIpcQrStartRequest,
) -> DingDaResult<IpcResponse<ChannelIpcQrStartResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(|error| error.to_string())?;

    let existing = if request.account_id.trim().is_empty() {
        None
    } else {
        repo.list_accounts()
            .map_err(|error| error.to_string())?
            .into_iter()
            .find(|account| account.id == request.account_id)
    };

    let sidecar_request = ChannelSidecarQrStartRequest {
        account_id: existing
            .as_ref()
            .map(|account| account.id.clone())
            .unwrap_or_default(),
        trace_id: Some(request.account_id.clone()),
        platform: Some("xianyu".to_string()),
    };
    let sidecar = state.lifecycle.client();
    let response = crate::runtime::python::routes::channel_qr_start::call(sidecar, sidecar_request)
        .await
        .map_err(|error| error.to_string())?;

    // 登记 session → 登录目标映射（qr_check 时消费）。
    if let Some(session_id) = response.session_id.clone() {
        let target = match existing {
            Some(account) => QrTarget::Existing(account.id),
            None => QrTarget::Pending {
                kind: request.kind.clone().unwrap_or_else(|| "xianyu".to_string()),
                name: request
                    .name
                    .clone()
                    .unwrap_or_else(|| "闲鱼账号".to_string()),
            },
        };
        let mut map = qr_account_map()
            .lock()
            .map_err(|_| "扫码会话表锁损坏，请重启应用后重试".to_string())?;
        map.insert(session_id, target);
    }

    Ok(IpcResponse::ok(ChannelIpcQrStartResponse {
        ok: response.ok,
        status: response.status,
        session_id: response.session_id,
        qr_base64: response.qr_base64,
        detail: response.detail,
    }))
}

/// 轮询扫码状态；登录成功时更新账号凭据并连接。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn channel_qr_check(
    state: tauri::State<'_, crate::shared::state::AppState>,
    repo: State<'_, Arc<ChannelRepo>>,
    dispatcher: State<'_, Arc<ChannelDispatcher>>,
    request: ChannelIpcQrCheckRequest,
) -> DingDaResult<IpcResponse<ChannelIpcQrCheckResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(|error| error.to_string())?;

    let sidecar_request = ChannelSidecarQrCheckRequest {
        session_id: request.session_id.clone(),
        trace_id: Some(request.session_id.clone()),
        platform: Some("xianyu".to_string()),
    };
    let sidecar = state.lifecycle.client();
    let response = crate::runtime::python::routes::channel_qr_check::call(sidecar, sidecar_request)
        .await
        .map_err(|error| error.to_string())?;

    // 登录成功：绑定已有账号或自动创建账号，写入 cookies 并连接。
    if response.status == "success" {
        if let Some(cookies) = response.cookies.clone() {
            let credential = serde_json::to_string(&cookies).unwrap_or_default();
            let target = {
                let mut map = qr_account_map()
                    .lock()
                    .map_err(|_| "扫码会话表锁损坏，请重启应用后重试".to_string())?;
                map.remove(&request.session_id)
            };
            let accounts = repo.list_accounts().map_err(|error| error.to_string())?;
            let account = match target {
                Some(QrTarget::Existing(id)) => {
                    accounts.into_iter().find(|account| account.id == id)
                }
                Some(QrTarget::Pending { kind, name }) => Some(common::contracts::ChannelAccount {
                    id: Uuid::new_v4().to_string(),
                    kind,
                    name,
                    credential: String::new(),
                    enabled: true,
                }),
                None => accounts
                    .into_iter()
                    .find(|account| account.kind == "xianyu"),
            };
            if let Some(mut account) = account {
                account.credential = credential;
                repo.upsert_account(&account)
                    .map_err(|error| error.to_string())?;
                let _ = dispatcher.connect(&account).await;
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

/// 取消扫码登录。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-20
#[tauri::command]
pub async fn channel_qr_cancel(
    state: tauri::State<'_, crate::shared::state::AppState>,
    request: ChannelIpcQrCancelRequest,
) -> DingDaResult<IpcResponse<ChannelIpcQrCancelResponse>> {
    state
        .license
        .ensure_licensed()
        .await
        .map_err(|error| error.to_string())?;

    let sidecar_request = ChannelSidecarQrCancelRequest {
        session_id: request.session_id.clone(),
        trace_id: Some(request.session_id.clone()),
        platform: Some("xianyu".to_string()),
    };
    let sidecar = state.lifecycle.client();
    let response =
        crate::runtime::python::routes::channel_qr_cancel::call(sidecar, sidecar_request)
            .await
            .map_err(|error| error.to_string())?;

    Ok(IpcResponse::ok(ChannelIpcQrCancelResponse {
        ok: response.ok,
        detail: response.detail,
    }))
}

/// 推送一条渠道消息事件（历史同步 / 入站均可复用）。
fn emit_message(sink: &dyn EventSink, account_id: &str, message: ChannelMessage) {
    let event = AppEvent::ChannelMessage(ChannelMessageEvent {
        account_id: account_id.to_string(),
        message,
        suggestion: None,
    });
    if let Err(e) = emit(sink, &event) {
        warn!(%e, "emit channel message failed");
    }
}
