//! In-process pub/sub event bus.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, RwLock};

use thiserror::Error;

pub type SubscriptionId = u64;

#[derive(Debug, Error)]
pub enum EventError {
    #[error("publish failed: {0}")]
    PublishFailed(String),
    #[error("subscribe failed: {0}")]
    SubscribeFailed(String),
}

pub trait EventHandler: Send + Sync {
    fn handle(&self, topic: &str, payload: &[u8]) -> Result<(), EventError>;
}

pub trait EventBus: Send + Sync {
    fn publish(&self, topic: &str, payload: &[u8]) -> Result<(), EventError>;
    fn subscribe(
        &self,
        topic: &str,
        handler: Box<dyn EventHandler>,
    ) -> Result<SubscriptionId, EventError>;
}

struct Subscriber {
    _id: SubscriptionId,
    handler: Arc<dyn EventHandler>,
}

pub struct InMemoryEventBus {
    next_id: AtomicU64,
    topics: RwLock<HashMap<String, Vec<Subscriber>>>,
}

impl Default for InMemoryEventBus {
    fn default() -> Self {
        Self::new()
    }
}

impl InMemoryEventBus {
    pub fn new() -> Self {
        Self {
            next_id: AtomicU64::new(1),
            topics: RwLock::new(HashMap::new()),
        }
    }
}

impl EventBus for InMemoryEventBus {
    fn publish(&self, topic: &str, payload: &[u8]) -> Result<(), EventError> {
        let topics = self
            .topics
            .read()
            .map_err(|error| EventError::PublishFailed(error.to_string()))?;
        let Some(subscribers) = topics.get(topic) else {
            return Ok(());
        };

        let mut failures = Vec::new();
        for subscriber in subscribers {
            if let Err(error) = subscriber.handler.handle(topic, payload) {
                failures.push(error.to_string());
            }
        }

        if failures.is_empty() {
            Ok(())
        } else {
            Err(EventError::PublishFailed(failures.join("; ")))
        }
    }

    fn subscribe(
        &self,
        topic: &str,
        handler: Box<dyn EventHandler>,
    ) -> Result<SubscriptionId, EventError> {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        let mut topics = self
            .topics
            .write()
            .map_err(|error| EventError::SubscribeFailed(error.to_string()))?;
        topics
            .entry(topic.to_string())
            .or_default()
            .push(Subscriber {
                _id: id,
                handler: Arc::from(handler),
            });
        Ok(id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering as AtomicOrdering};

    struct CountingHandler {
        counter: Arc<AtomicUsize>,
    }

    impl EventHandler for CountingHandler {
        fn handle(&self, _topic: &str, _payload: &[u8]) -> Result<(), EventError> {
            self.counter.fetch_add(1, AtomicOrdering::SeqCst);
            Ok(())
        }
    }

    #[test]
    fn publish_notifies_all_subscribers() {
        let bus = InMemoryEventBus::new();
        let counter = Arc::new(AtomicUsize::new(0));
        let handler_a = Box::new(CountingHandler {
            counter: counter.clone(),
        });
        let handler_b = Box::new(CountingHandler {
            counter: counter.clone(),
        });

        bus.subscribe("runtime/sidecar/restarted", handler_a).ok();
        bus.subscribe("runtime/sidecar/restarted", handler_b).ok();
        bus.publish("runtime/sidecar/restarted", br#"{"event_id":"1"}"#)
            .ok();

        assert_eq!(counter.load(AtomicOrdering::SeqCst), 2);
    }
}
