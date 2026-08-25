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
