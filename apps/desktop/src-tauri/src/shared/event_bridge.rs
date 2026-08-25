//! kernel EventBus → Tauri emit 转发器。
//!
//! 将进程内 `InMemoryEventBus` 上发布的 runtime/* 事件转发到前端
//! （`runtime/error` / `runtime/sidecar/restarted`），接通 Rust 侧事件推送。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-18

use crate::infra::event::{EventError, EventHandler};
use tauri::{AppHandle, Emitter};

/// 将 `crate::infra::event::EventBus` 事件桥接到 `tauri::AppHandle::emit`。
///
/// 作者：Xiaoman
/// 创建时间：2026-08-18
#[derive(Clone)]
pub struct BusToTauri {
    app: AppHandle,
}

impl BusToTauri {
    /// 构造转发器。
    ///
    /// 作者：Xiaoman
    /// 创建时间：2026-08-18
    ///
    /// # 参数
    /// - `app` — Tauri 应用句柄
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
