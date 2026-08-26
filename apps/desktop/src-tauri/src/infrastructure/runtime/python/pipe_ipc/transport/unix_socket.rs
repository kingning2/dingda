//! Unix Domain Socket 客户端（Python 侧 bind/listen）。

use std::time::Duration;

use async_trait::async_trait;
use tokio::net::UnixStream;

use crate::infrastructure::runtime::python::pipe_ipc::endpoint::IpcEndpoint;
use crate::infrastructure::runtime::python::pipe_ipc::error::IpcError;
use crate::infrastructure::runtime::python::pipe_ipc::framing::{read_frame, write_frame};
use crate::infrastructure::runtime::python::pipe_ipc::transport::ConnectedStream;

use super::Transport;

pub async fn connect(endpoint: &IpcEndpoint) -> Result<ConnectedStream, IpcError> {
    let stream = UnixStream::connect(endpoint.path())
        .await
        .map_err(|e| IpcError::ConnectionFailed(format!("unix socket connect: {e}")))?;
    let (reader, writer) = stream.into_split();
    Ok(ConnectedStream {
        reader: Box::new(reader),
        writer: Box::new(writer),
    })
}

/// 满足规格的 Transport 包装（Session 实际使用 [`connect`] 拆分流）。
#[allow(dead_code)]
pub struct UnixSocketTransport {
    endpoint: IpcEndpoint,
    stream: Option<UnixStream>,
}

#[allow(dead_code)]
impl UnixSocketTransport {
    #[must_use]
    pub fn new(endpoint: IpcEndpoint) -> Self {
        Self {
            endpoint,
            stream: None,
        }
    }
}

#[async_trait]
impl Transport for UnixSocketTransport {
    async fn connect(&mut self) -> Result<(), IpcError> {
        let mut last = IpcError::ConnectionFailed("not attempted".into());
        for _ in 0..40 {
            match UnixStream::connect(self.endpoint.path()).await {
                Ok(stream) => {
                    self.stream = Some(stream);
                    return Ok(());
                }
                Err(e) => {
                    last = IpcError::ConnectionFailed(e.to_string());
                    tokio::time::sleep(Duration::from_millis(50)).await;
                }
            }
        }
        Err(last)
    }

    async fn send(&mut self, data: &[u8]) -> Result<(), IpcError> {
        let stream = self
            .stream
            .as_mut()
            .ok_or_else(|| IpcError::RuntimeUnavailable("unix socket not connected".into()))?;
        write_frame(stream, data).await
    }

    async fn recv(&mut self) -> Result<Vec<u8>, IpcError> {
        let stream = self
            .stream
            .as_mut()
            .ok_or_else(|| IpcError::RuntimeUnavailable("unix socket not connected".into()))?;
        read_frame(stream).await
    }

    async fn close(&mut self) -> Result<(), IpcError> {
        if let Some(mut stream) = self.stream.take() {
            use tokio::io::AsyncWriteExt;
            let _ = stream.shutdown().await;
        }
        Ok(())
    }
}
