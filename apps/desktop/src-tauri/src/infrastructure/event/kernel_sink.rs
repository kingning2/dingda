//! 将 `InMemoryEventBus` 接入 `contracts::events::EventSink`。

use std::sync::Arc;

use crate::contracts::errors::DingDaError;
use crate::contracts::events::EventSink;
use crate::contracts::DingDaResult;
use crate::infrastructure::event::{EventBus, InMemoryEventBus};

/// EventBus 的 `EventSink` 适配器（newtype）。
#[derive(Clone)]
pub struct KernelEventSink(pub Arc<InMemoryEventBus>);

impl KernelEventSink {
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
