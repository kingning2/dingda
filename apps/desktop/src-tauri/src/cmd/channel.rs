//! 渠道连接 / 会话 / 扫码 IPC。

pub use state::{
    channel_connect, channel_disconnect, channel_send, channel_state_get, channel_state_set,
};

#[cfg(platform_xianyu)]
pub use chat::{
    channel_fetch_history, channel_product_headinfo, channel_qr_cancel, channel_qr_check,
    channel_qr_start,
};
#[cfg(platform_xianyu)]
pub use connection::{
    account_connect, account_connection_state, account_cookie_renew, account_disconnect,
    to_channel_account,
};

#[cfg(platform_xianyu)]
pub use connection::sync_account_profile;

mod state {
    // 渠道通用 Tauri commands（状态 / 连接 / 发送）。
    //
    // 闲鱼专属历史 / 商品卡 / 渠道扫码见同目录 [`super::chat`]。

    use crate::contracts::contracts::{
        ChannelConversation, ChannelIpcConnectResponse, ChannelIpcDisconnectResponse,
        ChannelIpcSendRequest, ChannelIpcSendResponse, ChannelIpcStateRequest,
        ChannelIpcStateResponse,
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
}

#[cfg(platform_xianyu)]
mod chat {
    // 闲鱼专属渠道 IPC — 消息历史 / 商品卡 / 渠道扫码登录。
    //
    // 通用状态 / 连接 / 发送见同目录 [`super::state`]。

    use crate::contracts::contracts::{
        ChannelIpcQrCancelRequest, ChannelIpcQrCancelResponse, ChannelIpcQrCheckRequest,
        ChannelIpcQrCheckResponse, ChannelIpcQrStartRequest, ChannelIpcQrStartResponse,
        ChannelMessage, ChannelSidecarQrCancelRequest, ChannelSidecarQrCheckRequest,
        ChannelSidecarQrStartRequest,
    };
    use crate::contracts::events::{emit, AppEvent, ChannelMessageEvent, EventSink};
    use crate::contracts::{DingDaError, DingDaResult};
    use serde_json::Value;
    use std::collections::HashMap;
    use std::sync::{Arc, Mutex, OnceLock};
    use tauri::State;
    use tracing::{info, warn};
    use uuid::Uuid;

    use crate::cmd::IpcResponse;
    use crate::core::channel::dispatcher::ChannelDispatcher;
    use crate::core::channel::ChannelRepo;
    use crate::core::manager::python::routes::xianyu_message_headinfo::{
        self, MessageHeadinfoRequest,
    };
    use crate::core::manager::python::PythonWssBridge;
    use crate::utils::state::AppState;

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
        state: tauri::State<'_, crate::utils::state::AppState>,
        repo: State<'_, Arc<ChannelRepo>>,
        dispatcher: State<'_, Arc<ChannelDispatcher>>,
        wss_bridge: State<'_, Arc<PythonWssBridge>>,
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
                let cookie_list =
                    crate::core::store::cookies::parse_credential(&account.credential);
                crate::core::store::cookies::my_id(&cookie_list)
            });

        let cid = conversation
            .cid
            .clone()
            .unwrap_or_else(|| conversation.peer_id.clone());
        let history = if PythonWssBridge::use_python_sidecar()
            && wss_bridge.is_active(&conversation.account_id).await
        {
            wss_bridge
                .fetch_history(&conversation.account_id, &cid)
                .await?
        } else {
            dispatcher
                .fetch_history(&conversation.account_id, &cid)
                .await?
        };

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
        state: tauri::State<'_, AppState>,
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
        let cookie_str = crate::core::store::cookies::cookies_to_string(
            &crate::core::store::cookies::parse_credential(&account.credential),
        );
        let item_id = conversation.item_id.unwrap_or_default();
        let session_id = conversation
            .cid
            .clone()
            .unwrap_or_else(|| conversation.peer_id.clone());

        state
            .lifecycle
            .ensure_running()
            .await
            .map_err(|error| DingDaError::wrap(error.to_string()))?;
        let response = xianyu_message_headinfo::call(
            state.lifecycle.client(),
            MessageHeadinfoRequest {
                cookie: cookie_str,
                session_id,
                item_id,
            },
        )
        .await
        .map_err(|error| DingDaError::wrap(error.to_string()))?;
        if !response.ok {
            return Err(DingDaError::wrap(
                response
                    .message
                    .unwrap_or_else(|| "message.headinfo 失败".to_string()),
            ));
        }
        Ok(IpcResponse::ok(response.data.unwrap_or(Value::Null)))
    }

    /// 启动扫码登录：调 Python Playwright 打开登录页，截图二维码。
    /// 无账号（account_id 为空或不存在）时标记为登录成功后自动创建。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-20
    #[tauri::command]
    pub async fn channel_qr_start(
        state: tauri::State<'_, crate::utils::state::AppState>,
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
        let response =
            crate::core::manager::python::routes::channel_qr_start::call(sidecar, sidecar_request)
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
        state: tauri::State<'_, crate::utils::state::AppState>,
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
        let response =
            crate::core::manager::python::routes::channel_qr_check::call(sidecar, sidecar_request)
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
                    Some(QrTarget::Pending { kind, name }) => {
                        Some(crate::contracts::contracts::ChannelAccount {
                            id: Uuid::new_v4().to_string(),
                            kind,
                            name,
                            credential: String::new(),
                            enabled: true,
                        })
                    }
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
        state: tauri::State<'_, crate::utils::state::AppState>,
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
            crate::core::manager::python::routes::channel_qr_cancel::call(sidecar, sidecar_request)
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
}

#[cfg(platform_xianyu)]
mod connection {
    // 业务账号 → 渠道连接桥接 Tauri commands。
    //
    // 作者：Xiaoman
    // 创建时间：2026-08-18

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
                crate::contracts::DingDaError::validation(format!(
                    "账号不存在: {}",
                    request.account_id
                ))
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
}
