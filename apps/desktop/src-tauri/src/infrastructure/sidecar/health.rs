//! Python 健康检查 — 是否 ready / alive。

use std::sync::Arc;

use super::process::{SidecarLifecycle, SidecarLifecycleError};

/// Python 健康检查 — 包装现有 [`SidecarLifecycle::health_check`]。
pub struct PythonHealth {
    sidecar: Arc<SidecarLifecycle>,
}

impl PythonHealth {
    /// 包装现有 Sidecar 生命周期实现。
    #[allow(clippy::new_without_default)]
    pub fn new(sidecar: Arc<SidecarLifecycle>) -> Self {
        Self { sidecar }
    }

    /// 健康检查（HTTP ping）。
    pub async fn health_check(&self) -> Result<bool, SidecarLifecycleError> {
        self.sidecar.health_check().await
    }

    /// 是否存活（健康检查失败视为不存活）。
    pub async fn is_alive(&self) -> bool {
        self.health_check().await.unwrap_or(false)
    }
}
// Sidecar route binding: GET /v1/runtime/status (runtime snapshot).

use super::client::{SidecarClient, SidecarClientError};

pub async fn fetch(client: &SidecarClient) -> Result<PythonSidecarSnapshot, SidecarClientError> {
    client.get_json("/v1/runtime/status").await
}

#[cfg(test)]
mod tests {
    use super::PythonSidecarSnapshot;

    #[test]
    fn deserializes_minimal_snapshot() {
        let raw = r#"{"ok":true,"state":"running","uptime_ms":100}"#;
        let snap: PythonSidecarSnapshot = serde_json::from_str(raw).unwrap();
        assert!(snap.ok);
        assert_eq!(snap.state, "running");
        assert_eq!(snap.uptime_ms, 100);
        assert!(snap.active_ops.is_empty());
    }
}
// Python Sidecar 运行时快照 — Rust runtime 层聚合观测。

use serde::{Deserialize, Serialize};

/// Sidecar 活跃编排项。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonActiveOp {
    pub id: String,
    pub kind: String,
    pub stage: String,
    pub detail: String,
    pub started_ms: i64,
}

/// Sidecar 近期错误。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonRuntimeError {
    pub at_ms: i64,
    pub path: String,
    pub message: String,
    #[serde(default)]
    pub trace_id: String,
}

/// WSS 连接摘要。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonWssConnection {
    pub account_id: String,
    pub status: String,
    #[serde(default)]
    pub detail: String,
    pub queued_events: u32,
    pub auto_reply: bool,
}

/// Sidecar WSS 摘要。
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PythonWssSnapshot {
    #[serde(default)]
    pub connections: Vec<PythonWssConnection>,
}

/// Sidecar 请求统计。
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PythonSidecarStats {
    pub requests_total: u64,
    pub requests_failed: u64,
}

/// Python Sidecar 完整快照（来自 `GET /v1/runtime/status`）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonSidecarSnapshot {
    pub ok: bool,
    pub state: String,
    pub uptime_ms: u64,
    #[serde(default)]
    pub active_ops: Vec<PythonActiveOp>,
    #[serde(default)]
    pub recent_errors: Vec<PythonRuntimeError>,
    #[serde(default)]
    pub wss: PythonWssSnapshot,
    #[serde(default)]
    pub stats: PythonSidecarStats,
}

impl PythonSidecarSnapshot {
    /// 是否有进行中的编排。
    pub fn has_active_work(&self) -> bool {
        !self.active_ops.is_empty()
    }

    /// 最近一次错误（若有）。
    pub fn last_error(&self) -> Option<&PythonRuntimeError> {
        self.recent_errors.first()
    }
}
