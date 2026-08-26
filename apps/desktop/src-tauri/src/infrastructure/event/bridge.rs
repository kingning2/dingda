//! kernel EventBus → Tauri emit 转发器。
//!
//! 将进程内 `InMemoryEventBus` 上发布的 runtime/* 事件转发到前端。

use crate::infrastructure::event::{EventError, EventHandler};
use tauri::{AppHandle, Emitter};

/// 将 `crate::infrastructure::event::EventBus` 事件桥接到 `tauri::AppHandle::emit`。
#[derive(Clone)]
pub struct BusToTauri {
    app: AppHandle,
}

impl BusToTauri {
    pub fn new(app: AppHandle) -> Self {
        Self { app }
    }
}

impl EventHandler for BusToTauri {
    fn handle(&self, topic: &str, payload: &[u8]) -> Result<(), EventError> {
        let json: serde_json::Value = serde_json::from_slice(payload)
            .map_err(|error| EventError::PublishFailed(format!("bus 转发序列化失败: {error}")))?;
        self.app
            .emit(topic, json)
            .map_err(|error| EventError::PublishFailed(error.to_string()))
    }
}
