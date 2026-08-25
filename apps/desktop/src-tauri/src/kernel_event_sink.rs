//! 将 `crate::infra::InMemoryEventBus` 接入 `crate::contracts::events::EventSink`。
//!
//! 使用本地 newtype 满足 orphan rule，供 [`crate::contracts::events::emit`] 统一发布。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use crate::contracts::errors::DingDaError;
use crate::contracts::events::EventSink;
use crate::contracts::DingDaResult;
use crate::infra::event::{EventBus, InMemoryEventBus};
use std::sync::Arc;

/// EventBus 的 [`EventSink`] 适配器（newtype）。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Clone)]
pub struct KernelEventSink(pub Arc<InMemoryEventBus>);

impl KernelEventSink {
    /// 从共享 EventBus 构造。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    pub fn new(bus: Arc<InMemoryEventBus>) -> Self {
        Self(bus)
    }
}

impl EventSink for KernelEventSink {
    fn publish(&self, topic: &str, payload: &[u8]) -> DingDaResult<()> {
        EventBus::publish(self.0.as_ref(), topic, payload)
            .map_err(|error| DingDaError::Internal(format!("event publish failed: {error}")))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::contracts::events::{emit, AccountAction, AccountEvent, AppEvent};
    use std::sync::Arc;

    #[test]
    fn bus_accepts_app_event() {
        let sink = KernelEventSink::new(Arc::new(InMemoryEventBus::new()));
        let event = AppEvent::Account(AccountEvent {
            owner_id: 1,
            account_id: "a".to_string(),
            display_name: String::new(),
            action: AccountAction::Created,
        });
        emit(&sink, &event).expect("emit via bus");
    }
}
