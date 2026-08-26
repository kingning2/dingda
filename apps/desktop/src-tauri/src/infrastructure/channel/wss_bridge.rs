//! Python Sidecar WSS 桥 — Rust 启停长连接，经 pipe Event 接收入站并交给 [`ChannelCoordinator`]。

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use crate::application::channel::coordinator::ChannelCoordinator;
use crate::config::ConfigStore;
use crate::contracts::contracts::{
    AiIpcConfigResponse, ChannelAccount, ChannelCookie, ChannelSettings,
};
use crate::contracts::DingDaResult;
use crate::domain::account::{AccountService, AccountStore, AccountUpdate};
use crate::domain::channel::{
    ChannelDispatcher, ChannelInboundMessage, ConnectionState, ConversationSync, HistoryMessage,
    InboundListener,
};
use crate::infrastructure::channel::sidecar::{
    ws_connect::{self, WsConnectRequest},
    ws_disconnect::{self, WsDisconnectRequest},
    ws_history::{self, WsHistoryRequest},
    ws_send::{self, WsSendRequest},
};
use crate::infrastructure::runtime::python::SidecarLifecycle;
use crate::infrastructure::storage::cookies::parse_credential;
use crate::infrastructure::storage::ChannelRepo;
use serde_json::Value;
use tokio::sync::broadcast::error::RecvError;
use tokio::sync::RwLock;

const WS_EVENT_METHOD: &str = "ws.event";

struct SessionMeta {
    state: ConnectionState,
}

/// Sidecar WSS 连接桥。
pub struct PythonWssBridge {
    sidecar: Arc<SidecarLifecycle>,
    coordinator: Arc<ChannelCoordinator>,
    channel_repo: Arc<ChannelRepo>,
    config_store: Arc<ConfigStore>,
    sessions: Arc<RwLock<HashMap<String, SessionMeta>>>,
    /// push 泵已订阅当前 IPC session。
    push_attached: Arc<AtomicBool>,
}

impl PythonWssBridge {
    /// 组装桥接器并启动 pipe Event 监听泵。
    pub fn new(
        sidecar: Arc<SidecarLifecycle>,
        coordinator: Arc<ChannelCoordinator>,
        channel_repo: Arc<ChannelRepo>,
        config_store: Arc<ConfigStore>,
        account_store: Arc<dyn AccountStore>,
    ) -> Self {
        let sessions = Arc::new(RwLock::new(HashMap::new()));
        let push_attached = Arc::new(AtomicBool::new(false));
        spawn_push_pump(
            sidecar.clone(),
            coordinator.clone(),
            sessions.clone(),
            account_store,
            push_attached.clone(),
        );
        Self {
            sidecar,
            coordinator,
            channel_repo,
            config_store,
            sessions,
            push_attached,
        }
    }

    /// 闲鱼 WSS 统一走 Python Sidecar。
    pub fn use_python_sidecar() -> bool {
        true
    }

    /// 账号是否由本桥管理。
    pub async fn is_active(&self, account_id: &str) -> bool {
        self.sessions.read().await.contains_key(account_id)
    }

    /// 建立 Sidecar WSS（入站由 pipe Event 推送）。
    pub async fn connect(&self, account: &ChannelAccount) -> DingDaResult<()> {
        if account.kind != "xianyu" {
            return Err(crate::contracts::DingDaError::validation(
                "Python WSS 仅支持闲鱼",
            ));
        }

        if let Some(existing) = self.sessions.read().await.get(&account.id) {
            if matches!(
                existing.state,
                ConnectionState::Connected | ConnectionState::Connecting
            ) {
                return Ok(());
            }
        }

        self.disconnect(&account.id).await?;

        InboundListener::on_state(
            self.coordinator.as_ref(),
            &account.id,
            ConnectionState::Connecting,
            None,
        )
        .await;

        self.sidecar
            .ensure_running()
            .await
            .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;
        self.wait_push_attached(Duration::from_secs(3)).await?;

        let cookies = parse_credential(&account.credential);
        if cookies.is_empty() {
            return Err(crate::contracts::DingDaError::validation("无法解析 Cookie"));
        }

        let cookie_values: Vec<Value> = cookies
            .iter()
            .filter_map(|cookie| serde_json::to_value(cookie).ok())
            .collect();

        let channel_settings = self
            .channel_repo
            .get_settings()
            .unwrap_or(ChannelSettings { auto_reply: false });
        let auto_reply = channel_settings.auto_reply;
        let ai_settings = if auto_reply {
            build_ai_settings_payload(&self.config_store).await
        } else {
            None
        };

        let response = ws_connect::call(
            self.sidecar.client(),
            WsConnectRequest {
                account_id: account.id.clone(),
                cookies: cookie_values,
                auto_reply,
                ai_settings,
            },
        )
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

        if !response.ok {
            let detail = response.message.unwrap_or_else(|| "连接失败".into());
            InboundListener::on_state(
                self.coordinator.as_ref(),
                &account.id,
                ConnectionState::Error,
                Some(detail.clone()),
            )
            .await;
            return Err(crate::contracts::DingDaError::wrap(detail));
        }

        self.sessions.write().await.insert(
            account.id.clone(),
            SessionMeta {
                state: ConnectionState::Connecting,
            },
        );
        Ok(())
    }

    /// 断开 Sidecar WSS。
    pub async fn disconnect(&self, account_id: &str) -> DingDaResult<()> {
        self.sessions.write().await.remove(account_id);

        if self.sidecar.ensure_running().await.is_ok() {
            let _ = ws_disconnect::call(
                self.sidecar.client(),
                WsDisconnectRequest {
                    account_id: account_id.to_string(),
                },
            )
            .await;
        }

        InboundListener::on_state(
            self.coordinator.as_ref(),
            account_id,
            ConnectionState::Disconnected,
            None,
        )
        .await;
        Ok(())
    }

    /// 经 Sidecar 发送文本消息。
    pub async fn send(
        &self,
        account_id: &str,
        cid: &str,
        peer_id: &str,
        text: &str,
    ) -> DingDaResult<String> {
        self.sidecar
            .ensure_running()
            .await
            .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

        let response = ws_send::call(
            self.sidecar.client(),
            WsSendRequest {
                account_id: account_id.to_string(),
                cid: cid.to_string(),
                peer_id: peer_id.to_string(),
                text: text.to_string(),
            },
        )
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

        if !response.ok {
            return Err(crate::contracts::DingDaError::wrap(
                response.message.unwrap_or_else(|| "发送失败".into()),
            ));
        }

        let message_id = format!("xianyu-{}", uuid::Uuid::new_v4());

        Ok(message_id)
    }

    /// 经 Sidecar 拉取会话历史。
    pub async fn fetch_history(
        &self,
        account_id: &str,
        cid: &str,
    ) -> DingDaResult<Vec<HistoryMessage>> {
        self.sidecar
            .ensure_running()
            .await
            .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

        let response = ws_history::call(
            self.sidecar.client(),
            WsHistoryRequest {
                account_id: account_id.to_string(),
                cid: cid.to_string(),
            },
        )
        .await
        .map_err(|error| crate::contracts::DingDaError::wrap(error.to_string()))?;

        if !response.ok {
            return Err(crate::contracts::DingDaError::wrap(
                response.message.unwrap_or_else(|| "拉取历史失败".into()),
            ));
        }

        Ok(response
            .messages
            .into_iter()
            .map(|item| HistoryMessage {
                sender_user_id: item.sender_user_id,
                sender_user_name: item.sender_user_name,
                content: item.content,
                created_at_ms: item.created_at_ms,
            })
            .collect())
    }

    /// 查询桥接管理的连接状态。
    pub async fn connection_state(&self, account_id: &str) -> ConnectionState {
        self.sessions
            .read()
            .await
            .get(account_id)
            .map(|session| session.state)
            .unwrap_or(ConnectionState::Disconnected)
    }

    async fn wait_push_attached(&self, timeout: Duration) -> DingDaResult<()> {
        let deadline = Instant::now() + timeout;
        while !self.push_attached.load(Ordering::Acquire) {
            if Instant::now() >= deadline {
                return Err(crate::contracts::DingDaError::unavailable(
                    "wss-push",
                    "pipe Event 监听未就绪",
                ));
            }
            let _ = self.sidecar.ensure_running().await;
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
        Ok(())
    }
}

fn spawn_push_pump(
    sidecar: Arc<SidecarLifecycle>,
    coordinator: Arc<ChannelCoordinator>,
    sessions: Arc<RwLock<HashMap<String, SessionMeta>>>,
    account_store: Arc<dyn AccountStore>,
    push_attached: Arc<AtomicBool>,
) {
    tauri::async_runtime::spawn(async move {
        loop {
            push_attached.store(false, Ordering::Release);
            if sidecar.ensure_running().await.is_err() {
                tokio::time::sleep(Duration::from_millis(200)).await;
                continue;
            }
            let mut rx = match sidecar.client().subscribe_events().await {
                Ok(rx) => rx,
                Err(error) => {
                    warn!(%error, "WSS push 订阅失败，将重试");
                    tokio::time::sleep(Duration::from_millis(200)).await;
                    continue;
                }
            };
            push_attached.store(true, Ordering::Release);
            info!("WSS pipe Event 监听已就绪");

            loop {
                match rx.recv().await {
                    Ok(event) if event.method == WS_EVENT_METHOD => {
                        let account_id = string_field(&event.params, "account_id", "");
                        if account_id.is_empty() {
                            continue;
                        }
                        dispatch_event(
                            coordinator.as_ref(),
                            &sessions,
                            account_store.as_ref(),
                            &account_id,
                            &event.params,
                        )
                        .await;
                    }
                    Ok(_) => {}
                    Err(RecvError::Lagged(skipped)) => {
                        warn!(skipped, "WSS push 事件落后，已跳过积压");
                    }
                    Err(RecvError::Closed) => {
                        warn!("WSS push 通道关闭，将重新订阅");
                        break;
                    }
                }
            }
            push_attached.store(false, Ordering::Release);
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
    });
}

/// 按环境选择 Sidecar WSS 或 Rust 调度器连接。
pub async fn connect_channel(
    bridge: &PythonWssBridge,
    dispatcher: &ChannelDispatcher,
    account: &ChannelAccount,
) -> DingDaResult<()> {
    if account.kind == "xianyu" && PythonWssBridge::use_python_sidecar() {
        bridge.connect(account).await
    } else {
        dispatcher.connect(account).await
    }
}

/// 按环境选择 Sidecar WSS 或 Rust 调度器断开。
pub async fn disconnect_channel(
    bridge: &PythonWssBridge,
    dispatcher: &ChannelDispatcher,
    account_id: &str,
    kind: &str,
) -> DingDaResult<()> {
    if kind == "xianyu" && PythonWssBridge::use_python_sidecar() {
        bridge.disconnect(account_id).await
    } else {
        dispatcher.disconnect(account_id).await
    }
}

/// 按环境查询连接状态。
pub async fn connection_state_for(
    bridge: &PythonWssBridge,
    dispatcher: &ChannelDispatcher,
    account_id: &str,
    kind: &str,
) -> ConnectionState {
    if kind == "xianyu" && PythonWssBridge::use_python_sidecar() {
        bridge.connection_state(account_id).await
    } else {
        dispatcher.connection_state(account_id).await
    }
}

async fn dispatch_event(
    coordinator: &ChannelCoordinator,
    sessions: &Arc<RwLock<HashMap<String, SessionMeta>>>,
    account_store: &dyn AccountStore,
    account_id: &str,
    event: &Value,
) {
    let event_type = event.get("type").and_then(Value::as_str).unwrap_or("");
    match event_type {
        "connecting" => {
            macros::apply_conn_state!(
                coordinator,
                sessions,
                account_id,
                ConnectionState::Connecting
            )
        }
        "connected" => {
            macros::apply_conn_state!(
                coordinator,
                sessions,
                account_id,
                ConnectionState::Connected
            )
        }
        "disconnected" => {
            macros::apply_conn_state!(
                coordinator,
                sessions,
                account_id,
                ConnectionState::Disconnected
            )
        }
        "auth_expired" => {
            macros::apply_conn_state!(
                coordinator,
                sessions,
                account_id,
                ConnectionState::Error,
                string_field(event, "detail", "登录态已过期")
            )
        }
        "error" => {
            macros::apply_conn_state!(
                coordinator,
                sessions,
                account_id,
                ConnectionState::Error,
                string_field(event, "detail", "连接异常")
            )
        }
        "status" => {
            coordinator.emit_ui_status(
                account_id,
                event
                    .get("state")
                    .and_then(Value::as_str)
                    .unwrap_or("error"),
                event
                    .get("detail")
                    .and_then(Value::as_str)
                    .map(str::to_string),
            );
        }
        "cookies_updated" => persist_renewed_cookies(account_store, account_id, event),
        "message" => {
            InboundListener::on_message(
                coordinator,
                ChannelInboundMessage {
                    account_id: string_field(event, "account_id", account_id),
                    peer_id: string_field(event, "peer_id", ""),
                    peer_name: string_field(event, "peer_name", ""),
                    item_id: string_field(event, "item_id", ""),
                    cid: string_field(event, "cid", ""),
                    content: string_field(event, "content", ""),
                    created_at_ms: event
                        .get("created_at_ms")
                        .and_then(Value::as_i64)
                        .unwrap_or(0),
                },
            )
            .await;
        }
        "session" => {
            let cid = string_field(event, "cid", "");
            InboundListener::on_conversation(
                coordinator,
                ConversationSync {
                    account_id: string_field(event, "account_id", account_id),
                    peer_id: string_field(event, "peer_id", &cid),
                    item_id: string_field(event, "item_id", ""),
                    item_title: string_field(event, "item_title", ""),
                    updated_at: string_field(event, "updated_at", ""),
                    cid,
                },
            )
            .await;
        }
        "outbound" => {
            let cid = string_field(event, "cid", "");
            let peer_id = string_field(event, "peer_id", "");
            let content = string_field(event, "content", "");
            if content.is_empty() || cid.is_empty() || peer_id.is_empty() {
                return;
            }
            if let Err(error) = coordinator
                .record_outbound(
                    account_id,
                    &cid,
                    &peer_id,
                    &string_field(event, "item_id", ""),
                    &content,
                    &string_field(event, "message_id", "xianyu-auto"),
                )
                .await
            {
                warn!(%error, account = %account_id, "auto_reply outbound 持久化失败");
            }
        }
        _ => {}
    }
}

fn persist_renewed_cookies(account_store: &dyn AccountStore, account_id: &str, event: &Value) {
    let Some(cookies_value) = event.get("cookies") else {
        return;
    };
    let Ok(cookies) = serde_json::from_value::<Vec<ChannelCookie>>(cookies_value.clone()) else {
        warn!(account = %account_id, "cookies_updated 解析失败");
        return;
    };
    let Ok(credential) = serde_json::to_string(&cookies) else {
        return;
    };
    let service = AccountService::new(account_store);
    match service.update(
        1,
        account_id,
        &AccountUpdate {
            cookie: Some(credential),
            ..Default::default()
        },
    ) {
        Ok(_) => info!(account = %account_id, "已写回 Python 续期 Cookie"),
        Err(error) => warn!(account = %account_id, %error, "写回续期 Cookie 失败"),
    }
}

async fn build_ai_settings_payload(config_store: &ConfigStore) -> Option<Value> {
    let config: AiIpcConfigResponse = config_store.ai_get().await.ok()?;
    let account = config.accounts.first()?;
    let provider = config
        .providers
        .iter()
        .find(|item| item.id == account.provider_id)?;
    let model = account
        .default_model
        .clone()
        .or_else(|| provider.default_model.clone())
        .unwrap_or_else(|| "qwen-plus".to_string());
    Some(serde_json::json!({
        "ai_enabled": true,
        "provider_type": provider.kind,
        "api_key": account.api_key,
        "base_url": provider.base_url.clone().unwrap_or_default(),
        "model_name": model,
        "max_bargain_rounds": 3,
        "max_discount_percent": 10,
        "max_discount_amount": 100,
    }))
}

fn string_field(event: &Value, key: &str, default: &str) -> String {
    event
        .get(key)
        .and_then(Value::as_str)
        .unwrap_or(default)
        .to_string()
}

async fn update_session_state(
    sessions: &Arc<RwLock<HashMap<String, SessionMeta>>>,
    account_id: &str,
    state: ConnectionState,
) {
    if let Some(session) = sessions.write().await.get_mut(account_id) {
        session.state = state;
    }
}
