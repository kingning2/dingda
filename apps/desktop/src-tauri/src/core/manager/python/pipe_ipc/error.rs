//! IPC 错误类型 — 不 panic，由 RuntimeManager / SidecarClient 处理。

use std::time::Duration;

#[derive(Debug, thiserror::Error)]
pub enum IpcError {
    #[error("RuntimeUnavailable: {0}")]
    RuntimeUnavailable(String),
    #[error("TransportClosed")]
    TransportClosed,
    #[error("ConnectionFailed: {0}")]
    ConnectionFailed(String),
    #[error("Timeout after {0:?}")]
    Timeout(Duration),
    #[error("ProtocolError: {0}")]
    ProtocolError(String),
    #[error("RpcError: {0}")]
    RpcFailed(String),
}
