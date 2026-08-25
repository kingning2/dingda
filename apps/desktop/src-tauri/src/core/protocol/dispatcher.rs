//! 渠道调度器 — 多账号并行生命周期 + 入站管线。
//!
//! 当前闲鱼连接由 Python Sidecar WSS 负责，进程内协议工厂从未注册
//! （`register_factory` 无调用方），本模块仅保留连接 / 断开 / 状态查询占位。

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use super::protocol::{
    ChannelAccount, ChannelKind, ChannelProtocol, ConnectionState, HistoryMessage,
};
use crate::contracts::DingDaResult;

/// 协议实例工厂 — 每次连接创建独立 [`ChannelProtocol`]（支持多账号并行）。
pub type ChannelProtocolFactory = Arc<dyn Fn() -> Arc<dyn ChannelProtocol> + Send + Sync>;

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
    pub fn new() -> Self {
        Self {
            factories: Arc::new(RwLock::new(HashMap::new())),
            active: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    async fn factory_for(&self, kind: ChannelKind) -> DingDaResult<ChannelProtocolFactory> {
        let map = self.factories.read().await;
        map.get(&kind).cloned().ok_or_else(|| {
            crate::contracts::DingDaError::not_found("channel factory", kind.to_string())
        })
    }

    /// 连接账号；每个账号持有独立协议实例，可与其他账号并行在线。
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
    pub async fn disconnect(&self, account_id: &str) -> DingDaResult<()> {
        if let Some(protocol) = self.active.write().await.remove(account_id) {
            protocol.disconnect().await?;
        }
        Ok(())
    }

    /// 查询指定账号的连接状态。
    pub async fn connection_state(&self, account_id: &str) -> ConnectionState {
        self.active
            .read()
            .await
            .get(account_id)
            .map(|protocol| protocol.connection_state())
            .unwrap_or(ConnectionState::Disconnected)
    }

    /// 发送消息；`cid` 为平台侧会话 id，`peer_id` 为会话对端 id。
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

    /// 拉取某会话的完整消息历史（透传平台实现）。
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
