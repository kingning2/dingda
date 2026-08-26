//! 平台 Transport 抽象。业务禁止直接依赖 Named Pipe / Unix Socket 类型。

use async_trait::async_trait;
use tokio::io::{AsyncRead, AsyncWrite};

use super::endpoint::IpcEndpoint;
use super::error::IpcError;

#[cfg(windows)]
mod named_pipe;
#[cfg(unix)]
mod unix_socket;

/// 跨平台字节流传输。连接后通过 [`Transport::into_split`] 拆成读写半边供 Session 使用。
#[async_trait]
pub trait Transport: Send {
    async fn connect(&mut self) -> Result<(), IpcError>;
    async fn send(&mut self, data: &[u8]) -> Result<(), IpcError>;
    async fn recv(&mut self) -> Result<Vec<u8>, IpcError>;
    async fn close(&mut self) -> Result<(), IpcError>;
}

/// 已连接的双向流（内部类型对业务隐藏）。
pub struct ConnectedStream {
    pub reader: Box<dyn AsyncRead + Unpin + Send>,
    pub writer: Box<dyn AsyncWrite + Unpin + Send>,
}

/// Rust 作为客户端连接 Python 已监听的端点（带重试）。
pub async fn connect_with_retry(
    endpoint: &IpcEndpoint,
    attempts: u32,
    interval_ms: u64,
) -> Result<ConnectedStream, IpcError> {
    let mut last = IpcError::ConnectionFailed("not attempted".into());
    for _ in 0..attempts {
        match connect_once(endpoint).await {
            Ok(stream) => return Ok(stream),
            Err(err) => {
                last = err;
                tokio::time::sleep(std::time::Duration::from_millis(interval_ms)).await;
            }
        }
    }
    Err(last)
}

async fn connect_once(endpoint: &IpcEndpoint) -> Result<ConnectedStream, IpcError> {
    #[cfg(windows)]
    {
        named_pipe::connect(endpoint).await
    }
    #[cfg(unix)]
    {
        unix_socket::connect(endpoint).await
    }
    #[cfg(not(any(windows, unix)))]
    {
        let _ = endpoint;
        Err(IpcError::ConnectionFailed(
            "IPC transport unsupported on this platform".into(),
        ))
    }
}
