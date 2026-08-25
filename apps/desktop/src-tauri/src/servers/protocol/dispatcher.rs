//! 渠道调度器 — 协议工厂 + 多账号并行生命周期 + 入站管线。
//!
//! 业务层通过 dispatcher 操作各平台协议，不直接依赖具体实现。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use super::protocol::{
    ChannelAccount, ChannelKind, ChannelProtocol, ConnectionState, HistoryMessage,
};
use crate::contracts::DingDaResult;

/// 协议实例工厂 — 每次连接创建独立 [`ChannelProtocol`]（支持多账号并行）。
pub type ChannelProtocolFactory = Arc<dyn Fn() -> Arc<dyn ChannelProtocol> + Send + Sync>;

/// 调度器错误。
#[derive(Debug, thiserror::Error)]
pub enum DispatcherError {
    #[error("unsupported channel kind: {0}")]
    UnsupportedKind(String),
    #[error("channel not registered: {0}")]
    NotRegistered(String),
    #[error("channel error: {0}")]
    Channel(String),
}

/// 多渠道调度器。
#[derive(Clone)]
pub struct ChannelDispatcher {
    /// kind → 协议工厂。
    factories: Arc<RwLock<HashMap<ChannelKind, ChannelProtocolFactory>>>,
    /// account_id → 该账号独占的协议实例。
    active: Arc<RwLock<HashMap<String, Arc<dyn ChannelProtocol>>>>,
}

impl Default for ChannelDispatcher {
    fn default() -> Self {
        Self::new()
    }
}

impl ChannelDispatcher {
    /// 创建空调度器。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn new() -> Self {
        Self {
            factories: Arc::new(RwLock::new(HashMap::new())),
            active: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// 注册平台协议工厂。新平台接入点：实现 trait 后在此登记。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-20
    ///
    /// # 参数
    ///
    /// * `kind` — 渠道类型
    /// * `factory` — 每次连接时创建新的协议实例
    pub fn register_factory(&self, kind: ChannelKind, factory: ChannelProtocolFactory) {
        let mut map = self.factories.blocking_write();
        map.insert(kind, factory);
    }

    async fn factory_for(&self, kind: ChannelKind) -> DingDaResult<ChannelProtocolFactory> {
        let map = self.factories.read().await;
        map.get(&kind).cloned().ok_or_else(|| {
            crate::contracts::DingDaError::not_found("channel factory", kind.to_string())
        })
    }

    /// 连接账号；每个账号持有独立协议实例，可与其他账号并行在线。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-20
    pub async fn connect(&self, account: &ChannelAccount) -> DingDaResult<()> {
        if let Some(existing) = self.active.read().await.get(&account.id) {
            if existing.connection_state() == ConnectionState::Connected {
                return Ok(());
            }
        }

        self.disconnect(&account.id).await?;

        let kind = ChannelKind::from_str(&account.kind).ok_or_else(|| {
            crate::contracts::DingDaError::validation(format!(
                "unsupported channel kind: {}",
                account.kind
            ))
        })?;
        let factory = self.factory_for(kind).await?;
        let protocol = factory();
        protocol.connect(account).await?;
        self.active
            .write()
            .await
            .insert(account.id.clone(), protocol);
        Ok(())
    }

    /// 断开账号并释放其协议实例。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub async fn disconnect(&self, account_id: &str) -> DingDaResult<()> {
        if let Some(protocol) = self.active.write().await.remove(account_id) {
            protocol.disconnect().await?;
        }
        Ok(())
    }

    /// 发送消息；`cid` 为平台侧会话 id，`peer_id` 为会话对端 id。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub async fn send(
        &self,
        account_id: &str,
        cid: &str,
        peer_id: &str,
        text: &str,
    ) -> DingDaResult<String> {
        let protocol = self
            .active
            .read()
            .await
            .get(account_id)
            .cloned()
            .ok_or_else(|| {
                crate::contracts::DingDaError::not_found("active channel", account_id.to_string())
            })?;
        protocol.send(cid, peer_id, text).await
    }

    /// 查询指定账号的连接状态。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-20
    pub async fn connection_state(&self, account_id: &str) -> ConnectionState {
        self.active
            .read()
            .await
            .get(account_id)
            .map(|protocol| protocol.connection_state())
            .unwrap_or(ConnectionState::Disconnected)
    }

    /// 列出当前已登记的账号及其连接状态。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-21
    ///
    /// # 返回值
    ///
    /// `(account_id, state)` 列表。
    pub async fn list_sessions(&self) -> Vec<(String, ConnectionState)> {
        self.active
            .read()
            .await
            .iter()
            .map(|(id, protocol)| (id.clone(), protocol.connection_state()))
            .collect()
    }

    /// 将已有协议实例挂入调度器（不触发 `connect`，用于开发态复用 Host 会话）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-21
    ///
    /// # 参数
    ///
    /// * `account_id` — 账号 id
    /// * `protocol` — 已绑定账号的协议实例
    pub async fn adopt(&self, account_id: String, protocol: Arc<dyn ChannelProtocol>) {
        self.active.write().await.insert(account_id, protocol);
    }

    /// 拉取某会话的完整消息历史（透传平台实现）。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-20
    pub async fn fetch_history(
        &self,
        account_id: &str,
        cid: &str,
    ) -> DingDaResult<Vec<HistoryMessage>> {
        let protocol = self
            .active
            .read()
            .await
            .get(account_id)
            .cloned()
            .ok_or_else(|| {
                crate::contracts::DingDaError::not_found("active channel", account_id.to_string())
            })?;
        protocol.fetch_history(cid).await
    }
}
