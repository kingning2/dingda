//! Rust ↔ Python 通信 — Sidecar HTTP 客户端。

use crate::infrastructure::runtime::python::client::SidecarClient;

/// Python Sidecar IPC 面 — 暴露类型化 HTTP 客户端。
///
/// 业务 IPC 命令仍经 `AppState.lifecycle.client()` 获取同一客户端；
/// 本模块把 IPC 面收敛到 Python Runtime，供运行时层自用。
pub struct PythonIpc {
    client: SidecarClient,
}

impl PythonIpc {
    /// 用现有 Sidecar 客户端组装 IPC 面。
    #[allow(clippy::new_without_default)]
    pub fn new(client: SidecarClient) -> Self {
        Self { client }
    }

    /// 底层 Sidecar 客户端。
    pub fn client(&self) -> &SidecarClient {
        &self.client
    }
}
