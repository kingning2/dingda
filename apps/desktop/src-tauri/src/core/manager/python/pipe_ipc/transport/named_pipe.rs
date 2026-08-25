//! Windows Named Pipe 客户端（Python 侧 CreateNamedPipe 监听）。

use std::time::Duration;

use async_trait::async_trait;
use tokio::net::windows::named_pipe::{ClientOptions, NamedPipeClient};

use crate::core::manager::python::pipe_ipc::endpoint::IpcEndpoint;
use crate::core::manager::python::pipe_ipc::error::IpcError;
use crate::core::manager::python::pipe_ipc::framing::{read_frame, write_frame};
use crate::core::manager::python::pipe_ipc::transport::ConnectedStream;

use super::Transport;

pub async fn connect(endpoint: &IpcEndpoint) -> Result<ConnectedStream, IpcError> {
    let name = endpoint.display();
    let client = ClientOptions::new()
        .open(&name)
        .map_err(|e| IpcError::ConnectionFailed(format!("named pipe open {name}: {e}")))?;
    let (reader, writer) = tokio::io::split(client);
    Ok(ConnectedStream {
        reader: Box::new(reader),
        writer: Box::new(writer),
    })
}

/// 满足规格的 Transport 包装（Session 实际使用 [`connect`] 拆分流）。
#[allow(dead_code)]
pub struct NamedPipeTransport {
    endpoint: IpcEndpoint,
    client: Option<NamedPipeClient>,
}

#[allow(dead_code)]
impl NamedPipeTransport {
    #[must_use]
    pub fn new(endpoint: IpcEndpoint) -> Self {
        Self {
            endpoint,
            client: None,
        }
    }
}

#[async_trait]
impl Transport for NamedPipeTransport {
    async fn connect(&mut self) -> Result<(), IpcError> {
        let name = self.endpoint.display();
        // 管道可能尚未创建：短暂重试。
        let mut last = IpcError::ConnectionFailed("not attempted".into());
        for _ in 0..40 {
            match ClientOptions::new().open(&name) {
                Ok(client) => {
                    self.client = Some(client);
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
        let client = self
            .client
            .as_mut()
            .ok_or_else(|| IpcError::RuntimeUnavailable("named pipe not connected".into()))?;
        write_frame(client, data).await
    }

    async fn recv(&mut self) -> Result<Vec<u8>, IpcError> {
        let client = self
            .client
            .as_mut()
            .ok_or_else(|| IpcError::RuntimeUnavailable("named pipe not connected".into()))?;
        read_frame(client).await
    }

    async fn close(&mut self) -> Result<(), IpcError> {
        if let Some(mut client) = self.client.take() {
            use tokio::io::AsyncWriteExt;
            let _ = client.shutdown().await;
        }
        Ok(())
    }
}
